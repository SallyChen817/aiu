from pathlib import Path
from PySide6.QtCore import QObject, QTimer, Signal
from agent.pi_client import PiClient
from agent.state import TaskState


class Controller(QObject):
    status = Signal(str, str)
    connection = Signal(bool, str)
    busy_changed = Signal(bool)
    models_changed = Signal(list, str)
    history = Signal(list)
    message = Signal(str, str)
    assistant = Signal(str)
    evidence = Signal(str)
    session_changed = Signal(str)
    notice = Signal(str)

    def __init__(self, store, settings, parent=None):
        super().__init__(parent)
        self.store, self.settings = store, settings
        self.client = PiClient(store, parent=self)
        self.task = TaskState()
        self.connected = False
        self.has_models = False
        self.available_models = []
        self.current_model = ''
        self.model_request = None
        self.project = ''
        self.active_project = ''
        self.session_file = None
        self.restart_pending = False
        self.shutting_down = False
        self.blocks = {}
        self.task_timer = QTimer(self)
        self.task_timer.setSingleShot(True)
        self.task_timer.timeout.connect(lambda: self.stop('任务超过 120 秒，已停止'))
        self.abort_timer = QTimer(self)
        self.abort_timer.setSingleShot(True)
        self.abort_timer.timeout.connect(self._force_stop)
        self.client.ready.connect(self._ready)
        self.client.event.connect(self._event)
        self.client.response.connect(self._response)
        self.client.failed.connect(self._failed)
        self.client.exited.connect(self._exited)

    def save(self):
        try:
            self.store.save(self.settings)
        except OSError:
            self.notice.emit('设置保存失败，请检查应用数据目录权限')

    def connect_project(self, project):
        if self.task.busy:
            self.notice.emit('请先停止当前任务，再切换项目')
            return
        try:
            path = Path(project).resolve(strict=True)
            if not path.is_dir():
                raise ValueError()
        except (OSError, ValueError):
            self.notice.emit('项目目录不存在，请重新选择')
            return
        self.project = str(path)
        self.settings['project'] = self.project
        self.save()
        self.connected = False
        self.model_request = None
        self.connection.emit(False, '正在启动 pi…')
        self.status.emit('thinking', '正在连接 pi')
        if self.client.running:
            self.restart_pending = True
            self.client.shutdown()
        else:
            self._start()

    def _start(self):
        self.restart_pending = False
        self.active_project = self.project
        stored = self.settings['sessions'].get(self.project)
        self.session_file = self.store.valid_session(stored)
        if stored and not self.session_file:
            self.notice.emit('旧会话文件已失效，将创建新会话')
            self.settings['sessions'].pop(self.project, None)
        self.client.start(self.project, session=self.session_file, model=self.settings.get('model', ''))

    def reconnect(self):
        if self.project:
            self.connect_project(self.project)
        else:
            self.notice.emit('请先选择项目目录')

    def _ready(self, data):
        if self.restart_pending or self.shutting_down:
            return
        self.connected = True
        self.has_models = bool(data['models'])
        state = data['state']
        model = state.get('model') or {}
        model_id = f"{model.get('provider', '')}/{model.get('id', '')}" if model else ''
        self.current_model = model_id
        self.available_models = data['models']
        self.models_changed.emit(data['models'], model_id)
        self.history.emit(data['messages'])
        self._session_state(state)
        if self.has_models:
            self.connection.emit(True, f'pi 已连接 · {model_id}（认证有效性以实际请求为准）')
            self.status.emit('idle', '已就绪，来看看你的项目')
        else:
            self.connection.emit(False, 'pi 已连接，但没有可用模型；请打开“模型配置说明”')
            self.status.emit('error', '请先配置模型')
            self.notice.emit('未找到可用模型。设置供应商环境变量或在本应用 pi 配置目录登录后，点击重连。')

    def _session_state(self, data):
        self.session_file = data.get('sessionFile')
        self.session_changed.emit(f"会话 {(data.get('sessionId') or '新建')[:12]} · 已有 {data.get('messageCount', 0)} 条消息")
        self._save_session()

    def _save_session(self):
        valid = self.store.valid_session(self.session_file)
        if valid and self.active_project:
            self.settings['sessions'][self.active_project] = valid
            self.save()

    def send(self, text, require_read=False):
        text = text.strip()
        if not text or self.task.busy:
            return
        if len(text) > 16000:
            self.notice.emit('单条消息最多 16000 字符')
            return
        # CLI slash commands are not part of the product's user-input surface.
        if text.startswith('/'):
            self.notice.emit('此界面只接收聊天消息，不执行 pi 斜杠命令')
            return
        if not self.connected or not self.has_models or self.model_request:
            self.notice.emit('请先选择项目并连接可用模型')
            return
        self.task.begin(require_read)
        self.blocks = {}
        self.busy_changed.emit(True)
        self._publish()
        self.message.emit('user', text)
        self.evidence.emit('── 新任务：工具活动 ──')
        try:
            user_name = self.settings['pet']['user_name']
            self.client.command('prompt', message=f'用户称呼：{user_name}\n用户请求：\n{text}')
            self.task_timer.start(120000)
        except (RuntimeError, ValueError):
            self._failed('无法发送消息，请重连 pi')

    def introduce_project(self):
        self.send('读取这个项目，介绍它的结构和主要功能。先列目录并阅读真实文件；引用依据的相对路径，区分事实和推测，说明未覆盖的部分。', require_read=True)

    def _publish(self):
        self.status.emit(self.task.state, self.task.progress)
        self.busy_changed.emit(self.task.busy)

    def _event(self, event):
        if not self.task.busy:
            return
        kind = event['type']
        if self.task.stopping and kind != 'agent_settled':
            return
        if kind == 'message_start' and event.get('message', {}).get('role') == 'assistant':
            self.blocks = {}
            self.message.emit('assistant', '')
        elif kind == 'message_update':
            update = event.get('assistantMessageEvent') or {}
            index = update.get('contentIndex', 0)
            if update.get('type') == 'text_delta':
                self.blocks[index] = self.blocks.get(index, '') + update.get('delta', '')
            elif update.get('type') == 'text_end':
                self.blocks[index] = update.get('content', '')
            else:
                return
            self.assistant.emit(''.join(self.blocks[k] for k in sorted(self.blocks)))
        elif kind == 'message_end' and event.get('message', {}).get('role') == 'assistant':
            message = event['message']
            text = ''.join(b.get('text', '') for b in message.get('content', []) if b.get('type') == 'text')
            if message.get('stopReason') == 'error':
                error = str(message.get('errorMessage', '')).lower()
                if any(word in error for word in ('401', '403', 'authentication', 'api key', 'invalid token', 'authorization')):
                    self.task.failure = '模型认证失败，请在本机更新凭据后重连'
                else:
                    self.task.failure = '模型请求失败，请检查模型名称、服务地址或网络'
                self.notice.emit(self.task.failure)
            self.assistant.emit(text)
        elif kind == 'tool_execution_start':
            name = '读取文本' if event.get('toolName') == 'project_read' else '列出文件'
            # Display only relative path; no raw arguments/results or diagnostic logs.
            path = str(event.get('args', {}).get('path', '.'))[:180]
            self.evidence.emit(f'开始 · {name} · {path}')
        elif kind == 'tool_execution_end':
            details = event.get('result', {}).get('details') or {}
            if event.get('isError'):
                self.evidence.emit('拒绝/失败 · 未计入成功读取证据')
            elif event.get('toolName') == 'project_read':
                self.evidence.emit(f"已读取 · {details.get('path', '?')} · {details.get('bytes', 0)} 字节")
            else:
                self.evidence.emit(f"已列出 · {details.get('count', 0)} 项" + ('（已截断）' if details.get('truncated') else ''))
        failure = self.task.failure
        action = self.task.consume(event)
        if failure and kind == 'message_end':
            self.task.failure = failure
        if action == 'abort':
            self._abort()
        if not self.task.busy:
            self.task_timer.stop()
            self.abort_timer.stop()
            self.evidence.emit(f'任务结束 · {self.task.progress} · {self.task.turns} 轮 / {self.task.tool_calls} 次工具')
            if self.connected:
                self.client.command('get_state')
        self._publish()

    def _response(self, record):
        command = record.get('command')
        if command == 'set_model':
            if not self.model_request or record.get('id') != self.model_request[0]:
                return
            _, requested = self.model_request
            self.model_request = None
            if record.get('success'):
                self.current_model = requested
                self.settings['model'] = requested
                self.save()
                self.notice.emit('模型已切换；实际可用性将在下一次请求时验证')
            else:
                self.notice.emit('切换模型失败，已保留原模型；请检查模型名称和认证配置')
            self.models_changed.emit(self.available_models, self.current_model)
            self.connection.emit(self.has_models, f'pi 已连接 · {self.current_model}')
            return
        if not record.get('success'):
            self._failed('pi 拒绝了请求，请检查模型配置或重连')
            return
        if command == 'get_state':
            self._session_state(record.get('data') or {})
        elif command == 'prompt' and self.task.busy:
            disposition = (record.get('data') or {}).get('disposition')
            if disposition == 'handled':
                self.task.fail('消息由 pi 命令处理，未启动模型任务')
                self.task_timer.stop()
                self._publish()

    def select_model(self, value):
        if self.task.busy or self.model_request or not self.connected or not isinstance(value, str) or '/' not in value:
            return
        provider, model_id = value.split('/', 1)
        try:
            rid = self.client.command('set_model', provider=provider, modelId=model_id)
            self.model_request = (rid, value)
            self.connection.emit(False, '正在切换模型，请稍候…')
        except RuntimeError:
            self.notice.emit('切换模型失败，请重连')

    def reset_model(self):
        if self.task.busy:
            self.notice.emit('请先停止当前任务')
            return
        self.settings['model'] = ''
        self.model_request = None
        self.save()
        self.reconnect()

    def stop(self, reason=''):
        if not self.task.busy:
            return
        self.task.request_stop(reason)
        self._publish()
        self._abort()

    def _abort(self):
        self.task_timer.stop()
        try:
            self.client.command('abort')
        except RuntimeError:
            pass
        self.abort_timer.start(2000)

    def _force_stop(self):
        if not self.task.busy:
            return
        self.connected = False
        self.client.force_kill()
        self.task.finish_stop()
        self._publish()
        self.connection.emit(False, '任务已强制停止；点击重连继续，会话保留')

    def _failed(self, message):
        self.connected = False
        self.task_timer.stop()
        self.abort_timer.stop()
        self.task.fail(message)
        self._publish()
        self.connection.emit(False, message)
        self.notice.emit(message)

    def _exited(self):
        self.connected = False
        self._save_session()
        if self.shutting_down:
            return
        if self.restart_pending:
            QTimer.singleShot(0, self._start)

    def new_session(self):
        if self.task.busy:
            return
        self.settings['sessions'].pop(self.project, None)
        self.session_file = None
        self.save()
        self.reconnect()

    def shutdown(self):
        self.shutting_down = True
        self.task_timer.stop()
        self.abort_timer.stop()
        self._save_session()
        self.client.shutdown()
