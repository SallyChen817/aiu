import os
import pytest
from agent.file_tools import FileBoundaryError, list_files, read_text


def test_reads_actual_unicode_file_and_lists_filtered_tree(tmp_path):
    (tmp_path / '说明.md').write_text('真实项目\n第二行', encoding='utf-8')
    (tmp_path / '.env').write_text('SECRET=hidden')
    (tmp_path / 'credentials.json').write_text('{}')
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src' / 'app.py').write_text('print(42)')
    assert read_text(tmp_path, '说明.md')['text'] == '真实项目\n第二行'
    result = list_files(tmp_path, '.', 2)
    assert {x['path'] for x in result['entries']} == {'说明.md', 'src', 'src/app.py'}


@pytest.mark.parametrize('path', ['../outside.txt', 'C:\\Windows\\win.ini', '/etc/passwd', '\\\\server\\share', 'a.txt:stream', '.env', '.git/config', 'credentials.json', 'token.txt', 'private.key'])
def test_denies_escapes_and_sensitive_names(tmp_path, path):
    with pytest.raises(FileBoundaryError):
        read_text(tmp_path, path)


def test_size_binary_and_secret_content(tmp_path):
    for name, content in [('large.txt', b'x' * 65537), ('binary.txt', b'a\0b'), ('config.py', b'API_KEY = "not-a-real-key-123456789"')]:
        (tmp_path / name).write_bytes(content)
        with pytest.raises(FileBoundaryError):
            read_text(tmp_path, name)


def test_hardlinks_cannot_alias_credentials(tmp_path):
    (tmp_path / '.env').write_text('hidden')
    os.link(tmp_path / '.env', tmp_path / 'public.txt')
    with pytest.raises(FileBoundaryError):
        read_text(tmp_path, 'public.txt')


def test_links_outside_project_are_denied(tmp_path):
    target = tmp_path.parent / (tmp_path.name + '-outside.txt')
    target.write_text('outside')
    try:
        (tmp_path / 'link.txt').symlink_to(target)
    except OSError:
        pytest.skip('Windows symbolic link privilege unavailable; junction tested separately')
    with pytest.raises(FileBoundaryError):
        read_text(tmp_path, 'link.txt')


def test_listing_budget_and_depth(tmp_path):
    for i in range(220):
        (tmp_path / f'{i:03}.txt').write_text('ok')
    result = list_files(tmp_path, '.', 1)
    assert len(result['entries']) == 200
    assert result['truncated'] is True
    with pytest.raises(FileBoundaryError):
        list_files(tmp_path, '.', 10)


@pytest.mark.skipif(os.name != 'nt', reason='Windows junction boundary')
def test_windows_junction_cannot_escape_root(tmp_path):
    import subprocess
    outside = tmp_path.parent / (tmp_path.name + '-junction-outside')
    outside.mkdir()
    (outside / 'visible.txt').write_text('outside data')
    link = tmp_path / 'junction'
    env = os.environ.copy()
    env['XIAOMAO_TEST_JUNCTION'] = str(link)
    env['XIAOMAO_TEST_TARGET'] = str(outside)
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                    'New-Item -ItemType Junction -Path $env:XIAOMAO_TEST_JUNCTION -Target $env:XIAOMAO_TEST_TARGET | Out-Null'],
                   env=env, check=True, capture_output=True)
    try:
        with pytest.raises(FileBoundaryError):
            read_text(tmp_path, 'junction/visible.txt')
        assert list_files(tmp_path)['entries'] == []
    finally:
        # Removes the junction object, never the target tree.
        link.rmdir()
