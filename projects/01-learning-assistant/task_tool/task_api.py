from contextlib import closing
"""本地项目进度查询工具。只依赖 Python 标准库。"""
import argparse
from datetime import datetime, timezone
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import sys
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
STATUS_LABELS = {'done': '已完成', 'todo': '未完成', 'in_progress': '进行中'}
INITIAL_TASKS = [
    (1, '本地模型部署', 'done'),
    (2, 'Python API 调用', 'done'),
    (3, 'Dify 模型接入', 'done'),
    (4, '智能体工具接入', 'todo'),
    (5, '自己的 Web 应用', 'todo'),
]


def init_db(path):
    """只在首次建立任务表时写入用户确认的记录，不覆盖已有进度。"""
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tasks'"
        ).fetchone()
        if not exists:
            conn.execute('''CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('done','todo','in_progress')),
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
            )''')
            conn.executemany(
                'INSERT INTO tasks(id,title,status,source) VALUES (?,?,?,?)',
                [(i, title, status, '用户于 2026-10-09 确认的项目进度')
                 for i, title, status in INITIAL_TASKS],
            )


def read_tasks(path, status=None):
    # mode=ro 避免数据库丢失时悄悄新建一个空库。
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        sql = 'SELECT id,title,status,source,updated_at FROM tasks'
        params = ()
        if status:
            sql += ' WHERE status=?'
            params = (status,)
        tasks = [dict(row) for row in conn.execute(sql + ' ORDER BY id', params)]
    for task in tasks:
        task['status_label'] = STATUS_LABELS[task['status']]
    return {
        'project': '任务1：本地大模型、智能体与应用接入',
        'data_source': '本地 SQLite 数据库中的人工确认记录，非自动检测结果',
        'queried_at': datetime.now(timezone.utc).isoformat(),
        'count': len(tasks),
        'tasks': tasks,
    }


class TaskHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, db_path, **kwargs):
        self.db_path = db_path
        super().__init__(*args, **kwargs)

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/openapi.json':
            self.send_json(200, json.loads((ROOT / 'openapi.json').read_text(encoding='utf-8')))
            return
        if url.path != '/tasks':
            self.send_json(404, {'error': '接口不存在，请使用 GET /tasks'})
            return
        query = parse_qs(url.query, keep_blank_values=True)
        status = query.get('status', [''])[0]
        if set(query) - {'status'} or len(query.get('status', [])) > 1:
            self.send_json(400, {'error': '仅支持一个可选的 status 参数'})
            return
        if status and status not in STATUS_LABELS:
            self.send_json(400, {'error': 'status 必须为 done、todo 或 in_progress'})
            return
        try:
            data = read_tasks(self.db_path, status or None)
        except sqlite3.Error:
            self.log_error('SQLite query failed')
            self.send_json(503, {'error': '任务数据库读取失败，请稍后重试；不能据此判断任务进度'})
            return
        self.send_json(200, data)



def make_server(db_path, host, port):
    return ThreadingHTTPServer((host, port), partial(TaskHandler, db_path=Path(db_path)))


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--db', type=Path, default=ROOT / 'tasks.db')
    args = parser.parse_args()
    init_db(args.db)
    server = make_server(args.db, args.host, args.port)
    print(f'查询地址：http://localhost:{server.server_port}/tasks', flush=True)
    print(f'数据库：{args.db.resolve()}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
