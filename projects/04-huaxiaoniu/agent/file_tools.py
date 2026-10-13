"""Only this module reads selected project content. No shell or network access.

Names/content filters are defense in depth, not a general secret classifier.
"""
import ctypes
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys

MAX_FILE_BYTES = 65536
MAX_ENTRIES = 200
EXCLUDED = {'node_modules', 'venv', '__pycache__', 'dist', 'build', 'vendor', 'coverage'}
TEXT_SUFFIXES = {'.py', '.pyi', '.md', '.txt', '.rst', '.js', '.jsx', '.ts', '.tsx', '.json', '.toml', '.yaml', '.yml', '.ini', '.cfg', '.css', '.scss', '.html', '.xml', '.sql', '.sh', '.ps1', '.bat', '.cmd', '.c', '.h', '.cpp', '.hpp', '.rs', '.go', '.java', '.kt', '.vue', '.svelte', '.lua', '.r'}
TEXT_NAMES = {'dockerfile', 'makefile', 'license', 'readme', 'requirements', 'cmakelists.txt'}
SENSITIVE_NAME = re.compile(r'(credential|secret|token|password|passwd|private|api[_-]?key|id_rsa|id_ed25519|auth[._-])', re.I)
SECRET_CONTENT = re.compile(r'-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|\b(?:sk-(?:ant-)?[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b|["\']?(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|client[_-]?secret)["\']?\s*[:=]\s*["\'][^"\'\r\n]{8,}["\']', re.I)


class FileBoundaryError(ValueError):
    pass


def _permitted_name(name: str) -> bool:
    return not (name.startswith('.') or name.lower() in EXCLUDED or SENSITIVE_NAME.search(name) or name.lower().endswith(('.pem', '.key', '.p12', '.pfx', '.keystore')))


def _root(root) -> Path:
    base = Path(root).resolve(strict=True)
    if not base.is_dir():
        raise FileBoundaryError('项目目录不可用')
    return base


def _candidate(base: Path, relative: str) -> Path:
    if not isinstance(relative, str) or '\0' in relative or ':' in relative or len(relative) > 1024:
        raise FileBoundaryError('路径格式不允许')
    win = PureWindowsPath(relative)
    if win.is_absolute() or win.drive or relative.startswith(('/', '\\')):
        raise FileBoundaryError('只允许项目内的相对路径')
    parts = relative.replace('\\', '/').split('/')
    if any(p == '..' or (p not in ('', '.') and not _permitted_name(p)) for p in parts):
        raise FileBoundaryError('路径越界或文件受保护')
    path = base
    try:
        for part in parts:
            if part in ('', '.'):
                continue
            path /= part
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise FileBoundaryError('不允许符号链接、junction 或其他重解析点')
        path.resolve(strict=True).relative_to(base)
    except (OSError, ValueError) as error:
        if isinstance(error, FileBoundaryError):
            raise
        raise FileBoundaryError('文件不存在或无法在项目边界内访问') from None
    return path


def _verify_open_handle(file, base: Path, expected: Path):
    """Validate the opened file, not just its pre-open name (Windows rename race)."""
    info = os.fstat(file.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise FileBoundaryError('只允许普通文件，拒绝硬链接')
    if info.st_size > MAX_FILE_BYTES:
        raise FileBoundaryError('文件超过 64 KiB 读取限制')
    if os.name == 'nt':
        import msvcrt
        get_name = ctypes.WinDLL('kernel32', use_last_error=True).GetFinalPathNameByHandleW
        get_name.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32]
        get_name.restype = ctypes.c_uint32
        buffer = ctypes.create_unicode_buffer(32768)
        count = get_name(msvcrt.get_osfhandle(file.fileno()), buffer, len(buffer), 0)
        if not count or count >= len(buffer):
            raise FileBoundaryError('无法验证文件句柄')
        name = buffer.value
        if name.startswith('\\\\?\\UNC\\'):
            name = '\\\\' + name[8:]
        elif name.startswith('\\\\?\\'):
            name = name[4:]
        final = Path(name)
    else:
        final = Path(os.path.realpath(f'/proc/self/fd/{file.fileno()}')) if Path('/proc/self/fd').exists() else expected.resolve(strict=True)
    try:
        relative = final.relative_to(base)
    except ValueError:
        raise FileBoundaryError('打开的文件已离开项目边界') from None
    if final != expected or any(not _permitted_name(p) for p in relative.parts):
        raise FileBoundaryError('文件路径已变化或受到保护')


def read_text(root, path: str) -> dict:
    base = _root(root)
    candidate = _candidate(base, path)
    if candidate.suffix.lower() not in TEXT_SUFFIXES and candidate.name.lower() not in TEXT_NAMES:
        raise FileBoundaryError('只允许受支持的文本文件类型')
    try:
        with candidate.open('rb') as file:
            _verify_open_handle(file, base, candidate)
            data = file.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise FileBoundaryError('文件超过 64 KiB 读取限制')
        text = data.decode('utf-8-sig').replace('\r\n', '\n')
        if '\0' in text:
            raise FileBoundaryError('不读取二进制文件')
        if SECRET_CONTENT.search(text):
            raise FileBoundaryError('检测到可能的凭据，已拒绝读取整个文件')
    except (OSError, UnicodeError):
        raise FileBoundaryError('无法读取此 UTF-8 文本文件') from None
    return {'path': candidate.relative_to(base).as_posix(), 'text': text, 'bytes': len(data), 'lines': len(text.splitlines())}


def list_files(root, path='.', depth=2) -> dict:
    if type(depth) is not int or not 1 <= depth <= 4:
        raise FileBoundaryError('depth 必须为 1 到 4')
    base = _root(root)
    start = _candidate(base, path)
    if not start.is_dir():
        raise FileBoundaryError('目标不是目录')
    entries = []
    pending = [(start, 0)]
    examined = 0
    truncated = False
    while pending:
        directory, level = pending.pop(0)
        _candidate(base, directory.relative_to(base).as_posix())
        try:
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    examined += 1
                    if examined > 2000 or len(entries) >= MAX_ENTRIES:
                        truncated = True
                        pending.clear()
                        break
                    if not _permitted_name(entry.name):
                        continue
                    relative = Path(entry.path).relative_to(base).as_posix()
                    try:
                        candidate = _candidate(base, relative)
                        info = candidate.lstat()
                    except FileBoundaryError:
                        continue
                    is_dir = stat.S_ISDIR(info.st_mode)
                    if not is_dir and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
                        continue
                    entries.append({'path': relative, 'type': 'directory' if is_dir else 'file'})
                    if is_dir and level + 1 < depth:
                        pending.append((candidate, level + 1))
        except OSError:
            raise FileBoundaryError('目录不可读取') from None
    return {'entries': sorted(entries, key=lambda x: x['path']), 'truncated': truncated, 'excluded': '隐藏文件、依赖/构建目录、凭据名称、链接'}


def main():
    # Fixed executable invoked by the trusted extension; request never becomes argv/code.
    try:
        raw = sys.stdin.buffer.read(8193)
        if len(raw) > 8192:
            raise FileBoundaryError('请求过大')
        request = json.loads(raw)
        root = os.environ['XIAOMAO_PROJECT_ROOT']
        if request.get('tool') == 'project_list':
            result = list_files(root, request.get('path', '.'), request.get('depth', 2))
        elif request.get('tool') == 'project_read':
            result = read_text(root, request['path'])
        else:
            raise FileBoundaryError('未开放的工具')
        output = {'ok': True, 'data': result}
    except (ValueError, OSError, KeyError, TypeError):
        # Never echo arbitrary input, environment values, or raw exception paths.
        output = {'ok': False, 'error': '读取被拒绝：检查相对路径、凭据过滤、文本编码和大小限制'}
    sys.stdout.buffer.write(json.dumps(output, ensure_ascii=False).encode('utf-8') + b'\n')


if __name__ == '__main__':
    main()
