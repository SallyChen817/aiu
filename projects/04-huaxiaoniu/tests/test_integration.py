from pathlib import Path
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from agent.controller import Controller
from storage import Store
from ui.chat_window import ChatWindow
from ui.pet_window import PetWindow
from tests.provider_fixture import ProviderFixture


@pytest.fixture
def harness(qtbot, tmp_path):
    fixture = ProviderFixture()
    store = Store(tmp_path / 'data')
    fixture.configure(store)
    settings = store.load()
    settings['model'] = 'harness-fixture/harness-test'
    controller = Controller(store, settings)
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'README.md').write_text('REAL_FILE_729\nA real file, read through the actual controlled worker.', encoding='utf-8')
    window = ChatWindow(controller)
    qtbot.addWidget(window)
    with qtbot.waitSignal(controller.client.ready, timeout=20000):
        controller.connect_project(str(project))
    yield controller, window, fixture, project
    controller.shutdown()
    qtbot.waitUntil(lambda: not controller.client.running, timeout=5000)
    fixture.close()


def test_real_pi_tools_to_ui_and_session_restore_with_protocol_fixture(harness, qtbot):
    controller, window, fixture, project = harness
    controller.introduce_project()
    qtbot.waitUntil(lambda: not controller.task.busy, timeout=20000)
    assert controller.task.state == 'done'
    assert controller.task.read_paths == ['README.md']
    assert 'REAL_FILE_729' in controller.task.assistant_text
    assert controller.task.tool_calls == 2
    assert any('已读取' in window.tools.item(i).text() for i in range(window.tools.count()))
    for request in fixture.requests:
        assert {tool['function']['name'] for tool in request['tools']} == {'project_list', 'project_read'}
    qtbot.waitUntil(lambda: controller.project in controller.store.load()['sessions'], timeout=3000)
    session = controller.store.load()['sessions'][controller.project]
    assert Path(session).is_file()
    with qtbot.waitSignal(controller.client.ready, timeout=20000) as ready:
        controller.reconnect()
    assert ready.args[0]['state']['sessionFile'] == session
    assert any('REAL_FILE_729' in record['text'] for record in window.records)
    with qtbot.waitSignal(controller.client.ready, timeout=20000) as fresh:
        controller.new_session()
    assert fresh.args[0]['messages'] == []
    assert fresh.args[0]['state']['sessionFile'] != session


def test_stop_while_model_waits_keeps_pet_responsive(harness, qtbot):
    controller, window, fixture, project = harness
    fixture.mode = 'hold'
    pet = PetWindow()
    qtbot.addWidget(pet)
    pet.show()
    controller.send('等待中的停止测试')
    qtbot.waitUntil(fixture.received.is_set, timeout=10000)
    phase = pet.phase
    old = pet.pos()
    qtbot.mousePress(pet, Qt.MouseButton.LeftButton, pos=QPoint(110, 120))
    qtbot.mouseMove(pet, QPoint(140, 140))
    qtbot.mouseRelease(pet, Qt.MouseButton.LeftButton, pos=QPoint(140, 140))
    qtbot.waitUntil(lambda: pet.phase != phase, timeout=1000)
    assert pet.pos() != old
    controller.stop()
    qtbot.waitUntil(lambda: not controller.task.busy, timeout=4000)
    assert controller.task.state == 'idle'
    assert not window.stop_button.isEnabled()
    assert window.choose_button.isEnabled()


def test_timeout_reports_failure_and_allows_recovery(harness, qtbot):
    controller, window, fixture, project = harness
    fixture.mode = 'hold'
    controller.send('超时测试')
    qtbot.waitUntil(fixture.received.is_set, timeout=10000)
    controller.task_timer.start(30)
    qtbot.waitUntil(lambda: not controller.task.busy, timeout=4000)
    assert controller.task.state == 'error'
    assert '120' in controller.task.progress
    assert window.choose_button.isEnabled()


def test_provider_auth_error_is_not_a_success(harness, qtbot):
    controller, window, fixture, project = harness
    fixture.mode = 'error'
    controller.introduce_project()
    qtbot.waitUntil(lambda: not controller.task.busy, timeout=10000)
    assert controller.task.state == 'error'
    assert '认证' in controller.task.progress
    assert not controller.task.read_paths
    assert window.choose_button.isEnabled()


def test_switching_projects_never_associates_old_session_with_new_root(harness, qtbot, tmp_path):
    controller, window, fixture, project = harness
    controller.introduce_project()
    qtbot.waitUntil(lambda: not controller.task.busy, timeout=20000)
    qtbot.waitUntil(lambda: controller.project in controller.store.load()['sessions'], timeout=3000)
    old_session = controller.store.load()['sessions'][str(project.resolve())]
    other = tmp_path / 'other-project'
    other.mkdir()
    with qtbot.waitSignal(controller.client.ready, timeout=20000) as ready:
        controller.connect_project(str(other))
    assert ready.args[0]['messages'] == []
    assert ready.args[0]['state']['sessionFile'] != old_session
    assert controller.store.load()['sessions'].get(str(other.resolve())) != old_session


def test_rejected_model_selection_keeps_previous_model_and_blocks_racing_send(harness, qtbot):
    controller, window, fixture, project = harness
    original = controller.settings['model']
    controller.select_model('harness-fixture/missing-model')
    assert not window.send_button.isEnabled()
    controller.send('must not race the model switch')
    assert not controller.task.busy
    qtbot.waitUntil(lambda: window.send_button.isEnabled(), timeout=5000)
    assert controller.settings['model'] == original
    assert controller.store.load()['model'] == original
    assert window.model_box.currentData() == original


def test_reset_model_clears_broken_override(harness, qtbot):
    controller, window, fixture, project = harness
    controller.settings['model'] = 'removed-provider/removed-model'
    controller.save()
    with qtbot.waitSignal(controller.client.ready, timeout=20000):
        controller.reset_model()
    assert controller.store.load()['model'] == ''


def test_unexpected_pi_exit_restores_controls_and_allows_reconnect(harness, qtbot):
    controller, window, fixture, project = harness
    fixture.mode = 'hold'
    controller.send('后台退出测试')
    qtbot.waitUntil(fixture.received.is_set, timeout=10000)
    controller.client.process.kill()
    qtbot.waitUntil(lambda: not controller.task.busy, timeout=3000)
    assert controller.task.state == 'error'
    assert window.choose_button.isEnabled()
    assert not window.stop_button.isEnabled()
    with qtbot.waitSignal(controller.client.ready, timeout=20000):
        controller.reconnect()
    assert window.send_button.isEnabled()


def test_repeated_tool_loop_stops_at_turn_budget(harness, qtbot):
    controller, window, fixture, project = harness
    fixture.mode = 'loop'
    controller.send('协议循环限制测试')
    qtbot.waitUntil(lambda: not controller.task.busy, timeout=20000)
    assert controller.task.state == 'error'
    assert '轮' in controller.task.progress
    assert len(fixture.requests) <= 12
    assert controller.task.tool_calls <= 12


def test_parallel_tool_batch_is_bounded(harness, qtbot):
    controller, window, fixture, project = harness
    fixture.mode = 'batch_limit'
    results = []
    controller.client.event.connect(lambda event: results.append(event) if event['type'] == 'tool_execution_end' else None)
    controller.send('并行工具预算测试')
    qtbot.waitUntil(lambda: not controller.task.busy, timeout=20000)
    assert len([r for r in results if not r.get('isError')]) <= 24
    assert controller.task.state == 'error'
    assert '工具' in controller.task.progress


def test_no_provider_configuration_shows_clear_message(qtbot, tmp_path, monkeypatch):
    import os
    for key in list(os.environ):
        if any(part in key for part in ('API_KEY', 'AUTH_TOKEN', 'OAUTH_TOKEN', 'AWS_', 'GOOGLE_APPLICATION_CREDENTIALS', 'GITHUB_TOKEN')):
            monkeypatch.delenv(key)
    store = Store(tmp_path / 'no-model-data')
    controller = Controller(store, store.load())
    window = ChatWindow(controller)
    qtbot.addWidget(window)
    try:
        with qtbot.waitSignal(controller.client.ready, timeout=20000):
            controller.connect_project(str(tmp_path))
        assert not window.send_button.isEnabled()
        assert '没有可用模型' in window.connection_label.text()
        assert window.badge.text() == '失败'
    finally:
        controller.shutdown()
        qtbot.waitUntil(lambda: not controller.client.running, timeout=5000)
