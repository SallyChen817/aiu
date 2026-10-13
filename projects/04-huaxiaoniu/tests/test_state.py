from agent.state import TaskState


def text_end(text='结构说明', reason='stop'):
    return {'type': 'message_end', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': text}], 'stopReason': reason}}


def test_prompt_ack_and_agent_end_do_not_claim_completion():
    state = TaskState()
    state.begin(require_read=True)
    for event in [{'type': 'response', 'success': True, 'command': 'prompt'}, {'type': 'agent_start'}, {'type': 'agent_end', 'messages': []}]:
        state.consume(event)
    assert state.busy
    assert state.state == 'thinking'
    state.consume(text_end())
    state.consume({'type': 'agent_settled', 'aborted': False})
    assert state.state == 'error'
    assert '读取' in state.progress


def test_real_tool_evidence_and_settled_complete_then_reset_next_task():
    state = TaskState()
    state.begin(require_read=True)
    state.consume({'type': 'tool_execution_start', 'toolName': 'project_read', 'toolCallId': 'a', 'args': {'path': 'README.md'}})
    assert state.state == 'working'
    state.consume({'type': 'tool_execution_end', 'toolName': 'project_read', 'toolCallId': 'a', 'isError': False, 'result': {'details': {'path': 'README.md', 'bytes': 10}}})
    state.consume(text_end())
    state.consume({'type': 'agent_end', 'messages': []})
    assert state.busy
    state.consume({'type': 'agent_settled', 'aborted': False})
    assert state.state == 'done' and not state.busy
    assert state.read_paths == ['README.md']
    state.begin(True)
    assert state.read_paths == [] and state.state == 'thinking'


def test_provider_error_cannot_be_success():
    state = TaskState()
    state.begin()
    state.consume(text_end('', 'error'))
    state.consume({'type': 'agent_settled', 'aborted': False})
    assert state.state == 'error'


def test_stop_wins_racing_completion_and_late_events():
    state = TaskState()
    state.begin()
    state.request_stop()
    state.consume(text_end())
    state.consume({'type': 'agent_settled', 'aborted': False})
    assert state.state == 'idle' and state.progress == '已停止'
    state.consume({'type': 'tool_execution_start', 'toolName': 'project_read'})
    assert state.state == 'idle'


def test_turn_budget_requests_abort_and_preserves_failure():
    state = TaskState(max_turns=2)
    state.begin()
    assert not state.consume({'type': 'turn_start'})
    assert not state.consume({'type': 'turn_start'})
    assert state.consume({'type': 'turn_start'}) == 'abort'
    state.consume({'type': 'agent_settled', 'aborted': True})
    assert state.state == 'error' and '轮' in state.progress


def test_tool_error_is_displayed_but_recovery_is_possible():
    state = TaskState()
    state.begin()
    state.consume({'type': 'tool_execution_end', 'toolName': 'project_read', 'toolCallId': 'a', 'isError': True, 'result': {}})
    assert not state.read_paths
    state.consume(text_end('受保护的文件无法读取。'))
    state.consume({'type': 'agent_settled', 'aborted': False})
    assert state.state == 'done'
