"""本地 AI 项目助手 Web 后端：python -X utf8 server.py。"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import threading
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from task_tool.task_api import read_tasks
from dify_client import DifyClient, DifyError

def read_list_tasks(path,list_id=None):
    conn=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        conn.row_factory=sqlite3.Row
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='task_lists'").fetchone():
            return read_tasks(path)
        lists=[dict(r) for r in conn.execute('SELECT id,name FROM task_lists ORDER BY id')]
        selected=next((x for x in lists if str(x['id'])==str(list_id)),None)
        if selected is None:selected=next((x for x in lists if x['id']==1),lists[0] if lists else None)
        rows=[dict(r) for r in conn.execute('SELECT id,title,status,source,updated_at,list_id FROM tasks WHERE list_id=? ORDER BY id',(selected['id'],))] if selected else []
        labels={'done':'已完成','todo':'未完成','in_progress':'进行中'}
        for row in rows:row['status_label']=labels.get(row['status'],row['status'])
        from datetime import datetime,timezone
        return {'lists':lists,'selected_list':selected,'tasks':rows,'count':len(rows),'queried_at':datetime.now(timezone.utc).isoformat()}
    finally:conn.close()


class WebServer(ThreadingHTTPServer):
    daemon_threads = True

    def load_config(self):
        try:
            return json.loads(self.config_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def save_config(self, config):
        temporary = self.config_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
        os.replace(temporary, self.config_path)


class Handler(BaseHTTPRequestHandler):
    def host_ok(self):
        try:
            host = urlsplit('http://' + self.headers.get('Host', ''))
            return host.hostname in ('127.0.0.1', 'localhost', '::1') and host.port == self.server.server_port
        except ValueError:
            return False

    def headers_for(self, status, content_type, length=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        if length is not None:
            self.send_header('Content-Length', str(length))
        self.end_headers()

    def send_json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.headers_for(status, 'application/json; charset=utf-8', len(body))
        self.wfile.write(body)

    def fail(self, status, message, code='request_failed'):
        self.send_json(status, {'error': message, 'code': code})

    def do_GET(self):
        if not self.host_ok():
            self.fail(403, '仅允许从本机地址访问。')
            return
        path = urlsplit(self.path).path
        if path == '/api/status':
            config = self.server.load_config()
            self.send_json(200, {'configured': bool(config.get('api_key')),
                'app_name': config.get('app_name', ''),
                'task_store_available': self.server.db_path.is_file()})
        elif path == '/api/tasks':
            try:
                data = read_list_tasks(self.server.db_path,parse_qs(urlsplit(self.path).query).get('list_id',[''])[0])
            except sqlite3.Error:
                self.fail(503, '任务数据库暂时无法读取，请检查 task_tool/tasks.db。', 'database_unavailable')
                return
            self.send_json(200, data)
        else:
            files = {'/': ('index.html', 'text/html; charset=utf-8'),
                     '/index.html': ('index.html', 'text/html; charset=utf-8'),
                     '/styles.css': ('styles.css', 'text/css; charset=utf-8'),
                     '/app.js': ('app.js', 'text/javascript; charset=utf-8')}
            if path not in files:
                self.fail(404, '页面不存在。')
                return
            name, kind = files[path]
            try:
                body = (ROOT / 'static' / name).read_bytes()
            except OSError:
                self.fail(404, '页面文件尚未就绪。')
                return
            self.headers_for(200, kind, len(body))
            self.wfile.write(body)

    def read_json(self):
        origin = self.headers.get('Origin')
        if not self.host_ok() or (origin and origin != 'http://' + self.headers.get('Host')):
            raise DifyError('只允许本地网页提交请求。', 'origin_denied', 403)
        if self.headers.get('X-Requested-With') != 'project-assistant':
            raise DifyError('请求缺少本地应用标记。', 'origin_denied', 403)
        if self.headers.get_content_type() != 'application/json':
            raise DifyError('请求格式必须是 JSON。', 'invalid_request', 400)
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = 0
        if length <= 0 or length > 32768:
            raise DifyError('请求为空或内容过长。', 'invalid_request', 400)
        self.connection.settimeout(15)
        try:
            value = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeError, TimeoutError):
            raise DifyError('请求 JSON 无效。', 'invalid_request', 400) from None
        if not isinstance(value, dict):
            raise DifyError('请求 JSON 必须是对象。', 'invalid_request', 400)
        return value

    def do_POST(self):
        try:
            data = self.read_json()
            path = urlsplit(self.path).path
            if path == '/api/config':
                self.configure(data)
            elif path == '/api/chat':
                self.chat(data)
            elif path in ('/api/form','/api/resume'):
                self.form(data,resume=path=='/api/resume')
            else:
                self.fail(404, '接口不存在。')
        except DifyError as error:
            self.fail(error.status, str(error), error.code)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (OSError, ValueError):
            self.fail(500, '本地请求处理失败，请检查服务和本地配置文件。', 'local_error')

    def configure(self, data):
        key = data.get('api_key', '')
        if not isinstance(key, str) or not re.fullmatch(r'app-[A-Za-z0-9_-]{4,240}', key.strip()):
            raise DifyError('请输入 Dify 应用中创建的 app- 开头的 API 密钥。', 'invalid_key', 400)
        key = key.strip()
        info = DifyClient(self.server.dify_url, key, timeout=15).validate()
        config = {'api_key': key, 'app_name': info.get('name', '学习任务助手')}
        self.server.save_config(config)
        self.send_json(200, {'configured': True, 'app_name': config['app_name']})

    def chat(self, data):
        query = data.get('query', '')
        user = data.get('user', '')
        conversation = data.get('conversation_id', '')
        if not isinstance(query, str) or not query.strip() or len(query) > 6000:
            raise DifyError('请输入 1 至 6000 字的问题。', 'invalid_query', 400)
        if not isinstance(user, str) or not re.fullmatch(r'web-[A-Za-z0-9_-]{1,100}', user):
            raise DifyError('会话标识无效，请刷新网页。', 'invalid_user', 400)
        if not isinstance(conversation, str) or len(conversation) > 200:
            raise DifyError('会话标识无效，请新建对话。', 'invalid_conversation', 400)
        config = self.server.load_config()
        if not config.get('api_key'):
            raise DifyError('请先点击“连接 Dify”，填写已发布应用的 API 密钥。', 'not_configured', 503)
        if not self.server.chat_lock.acquire(blocking=False):
            raise DifyError('当前有回答正在生成，请等待结束后再试。', 'busy', 409)
        try:
            self.headers_for(200, 'application/x-ndjson; charset=utf-8')
            client = DifyClient(self.server.dify_url, config['api_key'])
            try:
                for event in client.chat(query.strip(), conversation, user):
                    self.write_event(event)
            except DifyError as error:
                self.write_event({'type': 'error', 'message': str(error), 'code': error.code})
            except (OSError, ValueError, TypeError):
                self.write_event({'type': 'error', 'message': '回答传输异常，请重试或查看 Dify 运行记录。', 'code': 'stream_error'})
        finally:
            self.server.chat_lock.release()

    def write_event(self, event):
        self.wfile.write((json.dumps(event, ensure_ascii=False) + '\n').encode('utf-8'))
        self.wfile.flush()

    def form(self,data,resume=False):
        user=data.get('user','');run=data.get('workflow_run_id','');token=data.get('form_token','');action=data.get('action','')
        conversation=data.get('conversation_id','')
        if not isinstance(user,str) or not re.fullmatch(r'web-[A-Za-z0-9_-]{1,100}',user):raise DifyError('会话标识无效。','invalid_user',400)
        if not isinstance(run,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',run):raise DifyError('运行编号无效。','invalid_form',400)
        if not isinstance(conversation,str) or len(conversation)>200:raise DifyError('会话编号无效。','invalid_form',400)
        if not resume and (not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,512}',token) or action not in ('confirm','cancel')):raise DifyError('表单操作无效。','invalid_form',400)
        config=self.server.load_config()
        if not config.get('api_key'):raise DifyError('请先连接 Dify。','not_configured',503)
        if not self.server.chat_lock.acquire(blocking=False):raise DifyError('正在处理上一条请求，请稍候。','busy',409)
        try:
            self.headers_for(200,'application/x-ndjson; charset=utf-8')
            client=DifyClient(self.server.dify_url,config['api_key'])
            stream=client.resume(run,conversation,user) if resume else client.submit_form(token,action,run,conversation,user)
            try:
                for event in stream:self.write_event(event)
            except DifyError as error:self.write_event({'type':'error','message':str(error),'code':error.code})
        finally:self.server.chat_lock.release()


def make_server(host='127.0.0.1', port=8766, *, config_path=None, db_path=None, dify_url='http://localhost/v1'):
    server = WebServer((host, port), Handler)
    server.config_path = Path(config_path or ROOT / 'config.local.json')
    server.db_path = Path(db_path or ROOT.parent / 'task_tool' / 'tasks.db')
    server.dify_url = dify_url
    server.chat_lock = threading.Lock()
    return server


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    server = make_server(port=args.port)
    print(f'AI 项目助手：http://localhost:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
