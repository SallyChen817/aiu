"""Live pi/model verification; does not fabricate model or tool responses."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication, QTimer
from agent.pi_client import PiClient, APP_DIR
from storage import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', default=str(APP_DIR))
    parser.add_argument('--model', default='')
    parser.add_argument('--data-dir', default=str(APP_DIR / '.runtime/live-probe'))
    options = parser.parse_args()
    app = QCoreApplication([])
    store = Store(options.data_dir)
    client = PiClient(store)
    report = {'live_model': False, 'tool_reads': [], 'event_types': [], 'heartbeat_ticks': 0}
    seen = set()
    closing = False
    restoring = False
    session = None

    def finish(reason):
        nonlocal closing
        if closing:
            return
        closing = True
        report['result'] = reason
        print(json.dumps(report, ensure_ascii=False), flush=True)
        client.shutdown()
        if not client.running:
            app.quit()

    def ready(data):
        nonlocal restoring
        model = data['state'].get('model') or {}
        report['model'] = f"{model.get('provider', '')}/{model.get('id', '')}"
        report['tools'] = data['tools']
        if restoring:
            report['restored_messages'] = len(data['messages'])
            report['session_restored'] = len(data['messages']) > 0 and data['state'].get('sessionFile') == session
            finish('verified' if report['live_model'] and report.get('session_restored') else 'incomplete')
            return
        if not data['models']:
            finish('no_available_model')
            return
        print(json.dumps({'phase': 'requesting_live_model', 'model': report['model'], 'tools': data['tools']}, ensure_ascii=False), flush=True)
        client.command('prompt', message='读取这个项目，介绍它的结构和主要功能。必须先列出文件，然后至少读取一个真实源文件，以中文简短回答并注明依据路径。最多读取3个文件。')

    def event(record):
        kind = record['type']
        if kind not in seen:
            seen.add(kind)
            report['event_types'].append(kind)
        if kind == 'tool_execution_end' and record.get('toolName') == 'project_read' and not record.get('isError'):
            report['tool_reads'].append(record.get('result', {}).get('details'))
        elif kind == 'message_end':
            message = record.get('message', {})
            if message.get('role') == 'assistant':
                reason = message.get('stopReason')
                report['stop_reason'] = reason
                report['assistant_text_chars'] = sum(len(b.get('text', '')) for b in message.get('content', []) if b.get('type') == 'text')
                # Classify errors without disclosing raw errors, URLs or credentials.
                error = str(message.get('errorMessage', '')).lower()
                if error:
                    report['error_category'] = 'authentication' if any(x in error for x in ('401', '403', 'auth', 'key', 'token')) else 'connection' if any(x in error for x in ('connect', 'fetch', 'timeout', 'network')) else 'provider_error'
        elif kind == 'agent_settled':
            report['live_model'] = bool(report['tool_reads']) and report.get('stop_reason') == 'stop' and report.get('assistant_text_chars', 0) > 0
            client.command('get_state')

    def response(record):
        nonlocal session, restoring
        if not record.get('success'):
            finish('rpc_command_failed')
        elif record.get('command') == 'get_state':
            session = store.valid_session(record.get('data', {}).get('sessionFile'))
            report['session_persisted'] = bool(session)
            if session:
                restoring = True
                client.shutdown()
            else:
                finish('session_not_saved')

    def exited():
        if closing:
            app.quit()
        elif restoring:
            client.start(options.project, session=session, model=options.model)

    client.ready.connect(ready)
    client.event.connect(event)
    client.response.connect(response)
    client.failed.connect(lambda _message: finish('connection_failed'))
    client.exited.connect(exited)
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: report.update(heartbeat_ticks=report['heartbeat_ticks'] + 1))
    heartbeat.start(20)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(lambda: finish('live_request_timeout'))
    deadline.start(90000)
    client.start(options.project, model=options.model)
    app.exec()
    return 0 if report.get('result') == 'verified' else 2


if __name__ == '__main__':
    raise SystemExit(main())
