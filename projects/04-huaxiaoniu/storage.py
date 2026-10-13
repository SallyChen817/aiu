import copy
import json
import os
from pathlib import Path
import tempfile

DEFAULTS = {
    'version': 1,
    'pet': {'name': '华小牛', 'user_name': '同学'},
    'project': '', 'model': '', 'topmost': True,
    'sessions': {},
    'progression': {'task_count': 0, 'unlocked_decorations': []},
}


class Store:
    def __init__(self, directory=None):
        self.directory = Path(directory or os.environ.get('XIAOMAO_DATA_DIR') or Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'XiaomaoHarness').resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.sessions_dir = self.directory / 'sessions'
        self.sessions_dir.mkdir(exist_ok=True)
        self.pi_dir = self.directory / 'pi'
        self.pi_dir.mkdir(exist_ok=True)
        self.path = self.directory / 'settings.json'
        self.warning = ''

    def load(self):
        default = copy.deepcopy(DEFAULTS)
        if not self.path.exists():
            return default
        try:
            if self.path.stat().st_size > 1024 * 1024:
                raise ValueError()
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ValueError()
            for key in ('pet', 'sessions', 'progression'):
                if key in data and not isinstance(data[key], dict):
                    raise ValueError()
            if not isinstance(data.get('project', ''), str):
                raise ValueError()
            for key in ('name', 'user_name'):
                value = data.get('pet', {}).get(key)
                if isinstance(value, str) and value.strip():
                    default['pet'][key] = value.strip()[:32]
            default['project'] = data.get('project', '')
            default['model'] = data.get('model', '') if isinstance(data.get('model', ''), str) else ''
            default['topmost'] = data.get('topmost', True) is not False
            default['sessions'] = {k: v for k, v in data.get('sessions', {}).items() if isinstance(k, str) and isinstance(v, str)}
            # Reserved fields are inert; never execute or load resources from them.
            default['progression'] = data.get('progression', default['progression'])
            return default
        except (OSError, ValueError, TypeError):
            self.warning = '设置文件损坏或结构不兼容，已使用默认设置；原文件保留至下次保存'
            return default

    def save(self, data):
        # Whitelist stored fields. Model credentials belong to pi/env, never here.
        payload = {key: data.get(key, copy.deepcopy(value)) for key, value in DEFAULTS.items()}
        fd, name = tempfile.mkstemp(prefix='settings-', suffix='.tmp', dir=self.directory)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(name, self.path)
        finally:
            Path(name).unlink(missing_ok=True)

    def valid_session(self, value):
        if not isinstance(value, str) or not value:
            return None
        try:
            path = Path(value).resolve(strict=True)
            path.relative_to(self.sessions_dir.resolve())
            return str(path) if path.is_file() and path.suffix == '.jsonl' else None
        except (OSError, ValueError):
            return None
