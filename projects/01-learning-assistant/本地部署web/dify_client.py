"""Dify Chatflow API client and SSE-to-browser event adapter."""
import json
import socket
import urllib.error
import urllib.request
from urllib.parse import quote, urlencode


class DifyError(Exception):
    def __init__(self, message, code='dify_error', status=502):
        super().__init__(message)
        self.code = code
        self.status = status


def iter_sse(lines):
    data = []
    for raw in lines:
        line = raw.decode('utf-8').rstrip('\r\n')
        if not line:
            if data:
                yield json.loads('\n'.join(data))
                data = []
        elif line.startswith('data:'):
            value = line[5:].lstrip(' ')
            if value != '[DONE]':
                data.append(value)
    if data:
        yield json.loads('\n'.join(data))


def tool_event(log):
    if not isinstance(log, dict):
        return None
    label = str(log.get('label', ''))
    data = log.get('data') or {}
    output = data.get('output', {}) if isinstance(data, dict) else {}
    if not isinstance(output, dict):
        return None
    name = output.get('tool_call_name')
    if not name and not label.startswith('CALL '):
        return None
    name = name or label[5:]
    status = log.get('status', 'success')
    if status not in ('success', 'failed', 'error'):
        return None
    result = output.get('tool_response', '')
    if isinstance(result, str):
        # 自定义 API 工具可能同时附上文本及 JSON 消息，只解析第一份 JSON。
        start = result.find('{')
        if start >= 0:
            try:
                result, _ = json.JSONDecoder().raw_decode(result[start:])
            except json.JSONDecodeError:
                result = result[:8000]
        else:
            result = result[:8000]
    return {'type': 'tool', 'name': name, 'status': status, 'result': result,
            'id': log.get('id') or output.get('tool_call_id') or name}


class DifyClient:
    def __init__(self, base_url, api_key, timeout=300):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def open(self, path, payload=None):
        headers = {'Authorization': 'Bearer ' + self.api_key, 'Accept': 'application/json'}
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            headers['Content-Type'] = 'application/json'
            headers['Accept'] = 'text/event-stream'
        request = urllib.request.Request(self.base_url + path, data=body, headers=headers)
        try:
            return self.opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as error:
            status = error.code
            with error:
                try:
                    details = json.loads(error.read(16000))
                except (ValueError, UnicodeError):
                    details = {}
            code = details.get('code', '')
            if status in (401, 403):
                raise DifyError('Dify API 密钥无效或应用 API 未启用，请检查连接设置。', 'unauthorized', 401) from None
            if status == 412:
                raise DifyError('这张确认表单已提交或已过期。请重新查询任务；不要重复保存。', 'form_closed', 409) from None
            if 'workflow' in code or code in ('app_unavailable', 'app_not_found', 'agent_not_published'):
                raise DifyError('Dify 应用尚未发布或不可用，请先在应用右上角发布最新流程。', 'not_published', 503) from None
            if 'conversation' in code:
                raise DifyError('Dify 会话已失效，请点击“新对话”后重试。', 'conversation_invalid', 409) from None
            raise DifyError(f'Dify 请求失败（HTTP {status}），请检查应用发布状态和运行日志。') from None
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            raise DifyError('无法连接本地 Dify 或等待超时，请检查 Docker 和 Dify 是否运行。', 'connection_failed', 503) from None

    def validate(self):
        with self.open('/info') as response:
            info = json.load(response)
        if info.get('mode') not in (None, 'advanced-chat'):
            raise DifyError('请使用“学习任务助手”Chatflow 的应用 API 密钥。', 'wrong_app_type', 400)
        with self.open('/parameters') as response:
            json.load(response)
        return info

    def chat(self, query, conversation_id, user):
        payload = {'inputs': {}, 'query': query, 'response_mode': 'streaming',
                   'conversation_id': conversation_id, 'user': user}
        yield from self.stream('/chat-messages', payload, conversation_id)

    def submit_form(self, token, action, run_id, conversation_id, user):
        with self.open('/form/human_input/' + quote(token, safe=''), {'action':action,'inputs':{},'user':user}) as response:
            json.load(response)
        yield {'type':'form_submitted','action':action}
        yield from self.resume(run_id,conversation_id,user)

    def resume(self,run_id,conversation_id,user):
        path='/workflow/'+quote(run_id,safe='')+'/events?'+urlencode({'user':user,'include_state_snapshot':'true','continue_on_pause':'true'})
        yield from self.stream(path,None,conversation_id,resumed=True)

    def stream(self,path,payload,conversation_id,resumed=False):
        conversation = conversation_id
        message_id = ''
        has_text = False
        message_ended = False
        workflow_started = False
        workflow_finished = False
        seen_tools = set()
        form_pending = False
        run_id = ''
        try:
            with self.open(path, payload) as response:
                for event in iter_sse(response):
                    kind = event.get('event')
                    conversation = event.get('conversation_id') or conversation
                    message_id = event.get('message_id') or message_id
                    if kind == 'workflow_started':
                        workflow_started = True
                        run_id=event.get('workflow_run_id') or (event.get('data') or {}).get('id','')
                    elif kind == 'human_input_required':
                        if resumed:continue
                        data=event.get('data') or {}
                        if not data.get('form_token'):
                            raise DifyError('确认表单缺少 Webapp 访问凭据，请检查人工介入节点。','form_unavailable')
                        form_pending=True
                        yield {'type':'form','form_token':data['form_token'],'workflow_run_id':event.get('workflow_run_id') or run_id,
                               'content':data.get('form_content',''),'actions':data.get('actions',[]),'expiration_time':data.get('expiration_time'),
                               'conversation_id':conversation,'message_id':message_id}
                    elif kind == 'workflow_paused':
                        if resumed:continue
                        if not form_pending:raise DifyError('流程已暂停，但未收到可操作的确认表单。','form_unavailable')
                        yield {'type':'paused','conversation_id':conversation,'message_id':message_id}
                        return
                    elif kind in ('message', 'agent_message', 'message_replace'):
                        answer = event.get('answer') or ''
                        if answer:
                            has_text = True
                            yield {'type': 'replace' if kind == 'message_replace' else 'delta', 'text': answer}
                    elif kind in ('node_finished', 'agent_log'):
                        data = event.get('data') or {}
                        if kind=='node_finished' and data.get('node_type')=='tool':
                            outputs=data.get('outputs') or {};results=outputs.get('json') or []
                            failed=data.get('status') not in ('succeeded','success') or any(isinstance(x,dict) and x.get('status')=='error' for x in results)
                            yield {'type':'tool','id':data.get('id') or data.get('node_id'),'name':data.get('title','数据库工具'),
                                   'status':'failed' if failed else 'success','result':results or outputs.get('text','')}
                        if kind=='node_finished' and data.get('node_id') in ('verified','proposal'):
                            current=(data.get('outputs') or {}).get('current_list')
                            if current is not None:yield {'type':'current_list','list_id':current}
                        logs = [data] if kind == 'agent_log' else (data.get('outputs') or {}).get('json', [])
                        if not isinstance(logs, list):
                            logs = []
                        for log in logs:
                            tool = tool_event(log)
                            if tool and tool['id'] not in seen_tools:
                                seen_tools.add(tool['id'])
                                yield tool
                    elif kind == 'workflow_finished':
                        data = event.get('data') or {}
                        if data.get('status') not in ('succeeded', 'success'):
                            raise DifyError('Dify 工作流执行失败，请在 Dify 的运行记录中查看对应节点。', 'workflow_failed')
                        workflow_finished = True
                        if resumed:
                            output=data.get('outputs') or {}
                            final=output.get('answer') or ''
                            if final:
                                has_text=True
                                yield {'type':'replace','text':final}
                            if has_text:
                                yield {'type':'done','conversation_id':conversation,'message_id':message_id}
                                return
                    elif kind == 'error':
                        raise DifyError('Dify 执行时返回错误，请检查应用运行记录后重试。', 'workflow_failed')
                    elif kind == 'message_end':
                        if not has_text and not form_pending:
                            raise DifyError('Dify 未返回回答正文，请检查“直接回复”是否引用 Agent 的 text。', 'empty_answer')
                        message_ended = True
                    if message_ended and workflow_finished:
                        yield {'type': 'done', 'conversation_id': conversation, 'message_id': message_id}
                        return
            # 标注回复等快捷路径没有工作流，但仍须收到 message_end 并正常结束传输。
            if message_ended and not workflow_started:
                yield {'type': 'done', 'conversation_id': conversation, 'message_id': message_id}
                return
            raise DifyError('回答传输中断，未收到完成标记；已显示的内容可能不完整。', 'incomplete_stream')
        except (ValueError, UnicodeError):
            raise DifyError('Dify 返回了无法解析的数据，请检查应用 API 地址与服务状态。', 'invalid_response') from None
        except (TimeoutError, socket.timeout, urllib.error.URLError, ConnectionError):
            raise DifyError('生成回答时连接中断或超时，请稍后重试。', 'connection_failed') from None
