from pathlib import Path
from PySide6.QtCore import QTimer
from agent.pi_client import PiClient
from storage import Store


def test_real_pi_handshake_exposes_only_controlled_tools(qtbot, tmp_path):
    client = PiClient(Store(tmp_path / 'data'))
    beats = []
    timer = QTimer()
    timer.timeout.connect(lambda: beats.append(1))
    timer.start(10)
    try:
        with qtbot.waitSignal(client.ready, timeout=20000) as result:
            client.start(str(tmp_path))
        assert sorted(result.args[0]['tools']) == ['project_list', 'project_read']
        assert len(beats) > 3
        assert isinstance(result.args[0]['messages'], list)
    finally:
        timer.stop()
        client.shutdown()
        qtbot.waitUntil(lambda: not client.running, timeout=5000)


def test_missing_pi_reports_actionable_error(qtbot, tmp_path):
    client = PiClient(Store(tmp_path / 'data'), app_dir=tmp_path / 'missing')
    with qtbot.waitSignal(client.failed, timeout=1000) as result:
        client.start(str(tmp_path))
    assert 'npm ci' in result.args[0]
    assert not client.running


def test_model_config_cannot_execute_dynamic_credential_commands(qtbot, tmp_path):
    import json
    store = Store(tmp_path / 'data')
    (store.pi_dir / 'models.json').write_text(json.dumps({'providers': {'bad': {'apiKey': '!echo forbidden'}}}))
    client = PiClient(store)
    with qtbot.waitSignal(client.failed, timeout=1000) as result:
        client.start(str(tmp_path))
    assert '动态命令' in result.args[0]
    assert not client.running
