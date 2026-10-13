"""Local-only game server and optional Ollama debrief proxy. No dependencies."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import sys
import threading
import webbrowser
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent
MODEL = os.environ.get('THUNDER_MODEL', 'qwen3.5:4b')
PORT = int(os.environ.get('THUNDER_PORT', '8877'))

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def json_response(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if self.path != '/api/review':
            return self.json_response(404, {'error': '接口不存在'})
        origin = self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{PORT}', f'http://localhost:{PORT}'):
            return self.json_response(403, {'error': '仅允许本地游戏页面调用'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                raise ValueError('请求大小不正确')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('战绩格式不正确')
            stats = {}
            for key in ('score', 'kills', 'seconds', 'maxCombo', 'damage', 'missilesUsed'):
                value = data.get(key, 0)
                if type(value) is not int or not 0 <= value <= 10000000:
                    raise ValueError('战绩数值不正确')
                stats[key] = value
            if type(data.get('victory', False)) is not bool:
                raise ValueError('通关状态不正确')
            stats['victory'] = data.get('victory', False)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return self.json_response(400, {'error': str(exc)})
        payload = {'model': MODEL, 'stream': False, 'think': False,
                   'messages': [{'role': 'system', 'content': '你是雷霆空战的战术教官。根据提供的真实战绩，用中文给出不超过120字的简短点评和两条可操作建议。字段：score=得分，kills=击落数，seconds=时长秒，maxCombo=最高连击，damage=玩家受伤次数（不是输出伤害），missilesUsed=使用导弹弹药次数（一次发射两枚），victory=是否通关。不得编造命中率、飞行轨迹、火力不足或依赖某种操作等无法从数据得出的结论。真实规则：主炮始终自动射击，鼠标或方向键移动，空格发射自动追踪导弹；没有手动射击模式、手动锁定或切换武器按钮。4秒内连续击杀累计连击；拾取W升级主炮、M补导弹、+修复；受伤降低一级火力。只建议这些已有操作。先客观陈述战绩，再给两条建议。'},
                                {'role': 'user', 'content': json.dumps(stats, ensure_ascii=False)}],
                   'options': {'num_ctx': 4096, 'num_predict': 220}}
        request = urllib.request.Request('http://127.0.0.1:11434/api/chat',
                    data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=55) as response:
                result = json.load(response)
            text = result.get('message', {}).get('content', '').strip()
            if not text:
                raise ValueError('模型没有返回点评')
            self.json_response(200, {'text': text, 'model': MODEL})
        except Exception:
            self.json_response(503, {'error': f'无法获得本地模型点评，请检查 Ollama 和 {MODEL} 模型。游戏和积分不受影响。'})

if __name__ == '__main__':
    print(f'Thunder Squadron: http://127.0.0.1:{PORT}', flush=True)
    try:
        httpd = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
        if '--open' in sys.argv:
            threading.Timer(0.5, lambda: webbrowser.open(f'http://127.0.0.1:{PORT}')).start()
        httpd.serve_forever()
    except OSError as exc:
        print(f'Cannot start local server: {exc}', flush=True)
        raise SystemExit(1)
