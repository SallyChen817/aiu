"""Deterministic HTTP protocol fixture, NOT a real AI or a product demo mode.

Runs real pi/QProcess/tool workers against scripted OpenAI-compatible SSE.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading


class ProviderFixture:
    def __init__(self, mode='tools'):
        self.mode = mode
        self.requests = []
        self.received = threading.Event()
        self.release = threading.Event()
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def handle(self):
                try:
                    super().handle()
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                    pass

            def log_message(self, *_args):
                pass

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                fixture.requests.append(payload)
                fixture.received.set()
                if fixture.mode == 'hold':
                    fixture.release.wait(8)
                if fixture.mode == 'error':
                    self.send_response(401)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"error":{"message":"Fixture authentication failure","type":"authentication_error"}}')
                    return
                tool_messages = [m for m in payload['messages'] if m['role'] == 'tool']
                if fixture.mode == 'batch_limit':
                    delta = {'tool_calls': [{'index': i, 'id': f'batch-{i}', 'type': 'function', 'function': {'name': 'project_list', 'arguments': '{"path":".","depth":1}'}} for i in range(30)]}
                    reason = 'tool_calls'
                elif fixture.mode == 'loop':
                    delta = {'tool_calls': [{'index': 0, 'id': f'loop-{len(fixture.requests)}', 'type': 'function', 'function': {'name': 'project_list', 'arguments': '{"path":".","depth":1}'}}]}
                    reason = 'tool_calls'
                elif not tool_messages:
                    delta = {'tool_calls': [{'index': 0, 'id': 'list-call', 'type': 'function', 'function': {'name': 'project_list', 'arguments': '{"path":".","depth":2}'}}]}
                    reason = 'tool_calls'
                elif len(tool_messages) == 1:
                    delta = {'tool_calls': [{'index': 0, 'id': 'read-call', 'type': 'function', 'function': {'name': 'project_read', 'arguments': '{"path":"README.md"}'}}]}
                    reason = 'tool_calls'
                else:
                    text = str(tool_messages[-1]['content'])
                    delta = {'content': '协议测试回复（非真实 AI）：已读取 README.md。读取结果包含真实标记。' + (' REAL_FILE_729' if 'REAL_FILE_729' in text else ' MISSING')}
                    reason = 'stop'
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                try:
                    for part in [
                        {'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]},
                        {'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]},
                        {'choices': [{'index': 0, 'delta': {}, 'finish_reason': reason}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20}},
                    ]:
                        part.update(id='fixture', object='chat.completion.chunk', created=1, model='harness-test')
                        self.wfile.write(('data: ' + json.dumps(part) + '\n\n').encode())
                        self.wfile.flush()
                    self.wfile.write(b'data: [DONE]\n\n')
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def configure(self, store):
        data = {'providers': {'harness-fixture': {
            'baseUrl': f'http://127.0.0.1:{self.server.server_port}/v1',
            'api': 'openai-completions', 'apiKey': 'local-test-only-not-a-secret',
            'models': [{'id': 'harness-test', 'name': 'Protocol fixture (not AI)', 'reasoning': False, 'input': ['text'], 'contextWindow': 32000, 'maxTokens': 2048,
                        'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0}, 'compat': {'supportsStore': False}}],
        }}}
        (store.pi_dir / 'models.json').write_text(json.dumps(data), encoding='utf-8')

    def close(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
