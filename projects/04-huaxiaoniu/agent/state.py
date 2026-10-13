from dataclasses import dataclass, field


@dataclass
class TaskState:
    state: str = 'idle'
    progress: str = '等待选择项目'
    busy: bool = False
    stopping: bool = False
    require_read: bool = False
    max_turns: int = 12
    turns: int = 0
    tool_calls: int = 0
    read_paths: list[str] = field(default_factory=list)
    assistant_text: str = ''
    failure: str = ''

    def begin(self, require_read=False):
        self.state, self.progress = 'thinking', '正在请求模型'
        self.busy, self.stopping = True, False
        self.require_read = require_read
        self.turns = self.tool_calls = 0
        self.read_paths = []
        self.assistant_text = self.failure = ''

    def fail(self, reason, terminal=True):
        self.failure = reason
        self.state, self.progress = 'error', reason
        if terminal:
            self.busy = False

    def request_stop(self, reason=''):
        if not self.busy:
            return
        self.stopping = True
        if reason:
            self.failure = reason
        self.progress = '正在停止…'

    def finish_stop(self):
        self.busy = False
        self.state = 'error' if self.failure else 'idle'
        self.progress = self.failure or '已停止'

    def consume(self, event):
        if not self.busy:
            return None
        kind = event.get('type')
        if kind == 'agent_settled':
            if self.stopping or event.get('aborted'):
                self.finish_stop()
            elif self.failure:
                self.fail(self.failure)
            elif self.require_read and not self.read_paths:
                self.fail('本轮没有成功读取文件，无法确认项目介绍')
            elif not self.assistant_text.strip():
                self.fail('模型未返回有效文本')
            else:
                self.state, self.progress, self.busy = 'done', '任务完成 · 结果已展示', False
            return None
        if self.stopping:
            return None
        if kind in ('agent_start', 'turn_start'):
            self.state, self.progress = 'thinking', '正在思考项目内容'
            if kind == 'turn_start':
                self.turns += 1
                if self.turns > self.max_turns:
                    self.request_stop('超过模型轮数限制，已停止')
                    return 'abort'
        elif kind == 'tool_execution_start':
            self.tool_calls += 1
            self.state = 'working'
            self.progress = '正在读取文件' if event.get('toolName') == 'project_read' else '正在列出项目文件'
            if self.tool_calls > 24:
                self.request_stop('超过工具调用限制，已停止')
                return 'abort'
        elif kind == 'tool_execution_end':
            self.state = 'thinking'
            self.progress = '工具读取被拒绝，模型正在处理' if event.get('isError') else '读取完成，正在整理'
            details = event.get('result', {}).get('details') or {}
            if event.get('toolName') == 'project_read' and not event.get('isError') and isinstance(details.get('path'), str):
                self.read_paths.append(details['path'])
        elif kind == 'message_end':
            message = event.get('message', {})
            if message.get('role') == 'assistant':
                if message.get('stopReason') == 'error':
                    self.failure = '模型请求失败，请检查认证、模型和网络'
                elif message.get('stopReason') == 'aborted':
                    self.request_stop()
                else:
                    self.assistant_text = ''.join(b.get('text', '') for b in message.get('content', []) if b.get('type') == 'text')
        return None
