import json
from storage import Store


def test_restart_restores_profile_and_separates_project_sessions(tmp_path):
    store = Store(tmp_path)
    data = store.load()
    data['pet']['name'] = '华小牛'
    data['pet']['user_name'] = '同学'
    data['project'] = 'D:/project-a'
    data['sessions'] = {'D:/project-a': str(tmp_path / 'sessions' / 'a.jsonl')}
    store.save(data)
    assert Store(tmp_path).load() == data
    assert 'api_key' not in (tmp_path / 'settings.json').read_text(encoding='utf-8')


def test_corrupt_or_wrong_shape_settings_recover_safely(tmp_path):
    for content in ['{broken', '[]', '{"pet":null,"sessions":[],"project":42}']:
        (tmp_path / 'settings.json').write_text(content)
        store = Store(tmp_path)
        data = store.load()
        assert data['pet']['name'] == '华小牛'
        assert data['project'] == ''
        assert isinstance(data['sessions'], dict)
        assert store.warning


def test_session_reference_must_be_existing_app_owned_jsonl(tmp_path):
    store = Store(tmp_path)
    allowed = tmp_path / 'sessions' / 'a.jsonl'
    allowed.write_text('{}')
    assert store.valid_session(str(allowed)) == str(allowed.resolve())
    assert store.valid_session(str(tmp_path / 'settings.json')) is None
    assert store.valid_session(str(tmp_path.parent / 'outside.jsonl')) is None
