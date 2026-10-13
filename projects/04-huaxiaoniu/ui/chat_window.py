import html
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox,
    QPushButton, QSplitter, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

STYLE = '''
QMainWindow, QDialog { background: #F4F1E9; color: #283A34; }
QWidget { font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 13px; }
QLabel { color: #33473E; }
QLabel#title { font-size: 25px; font-weight: 700; }
QLabel#muted { color: #78857B; font-size: 12px; }
QLabel#badge { background: #DDE9DF; border-radius: 12px; padding: 5px 14px; font-weight: 600; }
QPushButton { background: #E7EBE2; color: #33473E; padding: 9px 15px; border: 1px solid #D8DED2; border-radius: 9px; }
QPushButton:hover { background: #DAE4D8; }
QPushButton:disabled { background: #EAEAE4; color: #A0A79D; }
QPushButton#primary { background: #385D49; color: white; border: 0; }
QPushButton#primary:hover { background: #46735A; }
QPushButton#primary:disabled { background: #A4B3A4; }
QPushButton#stop { color: #A04E44; background: #F0DFD8; border: 0; }
QTextBrowser, QTextEdit, QListWidget, QLineEdit, QComboBox { background: #FCFBF7; border: 1px solid #DEE2D7; border-radius: 10px; padding: 9px; color: #2F4037; selection-background-color: #B4CEBD; }
QListWidget { font-size: 12px; }
QSplitter::handle { background: transparent; width: 12px; }
'''


def message_text(message):
    content = message.get('content', '')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return '\n'.join(b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text')
    return ''


class ChatWindow(QMainWindow):
    profile_changed = Signal(str)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.records = []
        self.is_busy = False
        self.can_send = False
        self.dirty = False
        self.setWindowTitle('华小牛 · 项目陪伴工作台')
        self.resize(1060, 780)
        self.setMinimumSize(790, 610)
        self.setStyleSheet(STYLE)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(26, 23, 26, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        self.title = QLabel(f"{controller.settings['pet']['name']} / 项目陪伴工作台")
        self.title.setObjectName('title')
        heading.addWidget(self.title)
        subtitle = QLabel('一个会读项目、展示依据的 Python + pi 桌宠')
        subtitle.setObjectName('muted')
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch()
        self.badge = QLabel('待机')
        self.badge.setObjectName('badge')
        header.addWidget(self.badge)
        profile = QPushButton('宠物档案')
        profile.clicked.connect(self.edit_profile)
        header.addWidget(profile)
        layout.addLayout(header)

        project_row = QHBoxLayout()
        self.project_label = QLineEdit(controller.settings.get('project', ''))
        self.project_label.setReadOnly(True)
        self.project_label.setPlaceholderText('先选择一个本地项目目录')
        project_row.addWidget(self.project_label, 1)
        self.choose_button = QPushButton('选择项目')
        self.choose_button.clicked.connect(self.choose_project)
        project_row.addWidget(self.choose_button)
        self.intro_button = QPushButton('介绍这个项目')
        self.intro_button.setObjectName('primary')
        self.intro_button.clicked.connect(controller.introduce_project)
        project_row.addWidget(self.intro_button)
        layout.addLayout(project_row)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel('模型'))
        self.model_box = QComboBox()
        self.model_box.setMinimumWidth(250)
        self.model_box.activated.connect(lambda i: controller.select_model(self.model_box.itemData(i)))
        model_row.addWidget(self.model_box, 1)
        self.reconnect_button = QPushButton('重连')
        self.reconnect_button.clicked.connect(controller.reconnect)
        model_row.addWidget(self.reconnect_button)
        self.new_button = QPushButton('新对话')
        self.new_button.clicked.connect(controller.new_session)
        model_row.addWidget(self.new_button)
        config_button = QPushButton('模型配置说明')
        config_button.clicked.connect(self.show_model_help)
        model_row.addWidget(config_button)
        layout.addLayout(model_row)

        self.connection_label = QLabel('选择项目后连接 pi；无需在此输入 API 密钥')
        self.connection_label.setWordWrap(True)
        self.connection_label.setObjectName('muted')
        layout.addWidget(self.connection_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        conversation = QWidget()
        conversation_layout = QVBoxLayout(conversation)
        conversation_layout.setContentsMargins(0, 0, 0, 0)
        self.transcript = QTextBrowser()
        self.transcript.setOpenExternalLinks(False)
        self.transcript.setOpenLinks(False)
        conversation_layout.addWidget(self.transcript)
        splitter.addWidget(conversation)
        evidence_panel = QWidget()
        evidence_layout = QVBoxLayout(evidence_panel)
        evidence_layout.setContentsMargins(0, 0, 0, 0)
        evidence_layout.addWidget(QLabel('真实工具活动'))
        self.tools = QListWidget()
        self.tools.setWordWrap(True)
        evidence_layout.addWidget(self.tools, 1)
        boundary = QLabel('只读范围：当前项目\n\n列目录 / 读 UTF-8 文本\n单文件 ≤ 64 KiB\n任务 ≤ 120 秒\n最多 12 轮 / 24 次工具\n\n隐藏文件、凭据、链接、\n依赖和构建目录均过滤。')
        boundary.setObjectName('muted')
        boundary.setWordWrap(True)
        evidence_layout.addWidget(boundary)
        splitter.addWidget(evidence_panel)
        splitter.setSizes([690, 260])
        layout.addWidget(splitter, 1)

        self.input = QTextEdit()
        self.input.setPlaceholderText('告诉华小牛你想了解什么…  Ctrl+Enter 发送\n消息和读取的文件会发给所选模型；不要粘贴密钥。')
        self.input.setMaximumHeight(100)
        layout.addWidget(self.input)
        bottom = QHBoxLayout()
        self.progress = QLabel('等待选择项目')
        self.progress.setWordWrap(True)
        bottom.addWidget(self.progress, 1)
        self.stop_button = QPushButton('停止任务')
        self.stop_button.setObjectName('stop')
        self.stop_button.clicked.connect(lambda: controller.stop())
        bottom.addWidget(self.stop_button)
        self.send_button = QPushButton('发送  ↗')
        self.send_button.setObjectName('primary')
        self.send_button.clicked.connect(self.send)
        bottom.addWidget(self.send_button)
        layout.addLayout(bottom)
        self.session_label = QLabel('会话由 pi 保存 · 关闭此窗口仍保留桌宠，右键桌宠可退出')
        self.session_label.setObjectName('muted')
        layout.addWidget(self.session_label)

        QShortcut(QKeySequence('Ctrl+Return'), self, activated=self.send)
        QShortcut(QKeySequence('Ctrl+Enter'), self, activated=self.send)
        controller.status.connect(self.update_status)
        controller.connection.connect(self.update_connection)
        controller.busy_changed.connect(self.update_busy)
        controller.models_changed.connect(self.update_models)
        controller.message.connect(self.add_message)
        controller.assistant.connect(self.update_assistant)
        controller.history.connect(self.restore_history)
        controller.evidence.connect(self.add_evidence)
        controller.session_changed.connect(self.session_label.setText)
        controller.notice.connect(lambda text: self.add_message('notice', text))
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self.render_if_dirty)
        self.render_timer.start(50)
        self.add_message('notice', '你好，我是华小牛。选择一个项目，点“介绍这个项目”，我会调用受控工具阅读文件，并在右侧留下真实读取记录。')
        self.update_busy(False)

    def choose_project(self):
        folder = QFileDialog.getExistingDirectory(self, '选择华小牛可以读取的项目', self.project_label.text())
        if folder:
            self.project_label.setText(folder)
            self.controller.connect_project(folder)

    def send(self):
        if self.is_busy or not self.can_send:
            return
        text = self.input.toPlainText().strip()
        if text:
            self.controller.send(text)
            if self.controller.task.busy:
                self.input.clear()

    def update_connection(self, ready, text):
        self.can_send = ready
        self.connection_label.setText(text)
        self.update_busy(self.is_busy)

    def update_busy(self, busy):
        self.is_busy = busy
        for button in (self.choose_button, self.reconnect_button, self.new_button):
            button.setEnabled(not busy)
        self.model_box.setEnabled(not busy and self.can_send)
        self.send_button.setEnabled(not busy and self.can_send)
        self.intro_button.setEnabled(not busy and self.can_send)
        self.stop_button.setEnabled(busy)

    def update_status(self, state, text):
        self.badge.setText({'idle': '待机', 'thinking': '思考', 'working': '工作', 'done': '完成', 'error': '失败'}[state])
        self.progress.setText(text)

    def update_models(self, models, current):
        self.model_box.clear()
        for model in models:
            key = f"{model['provider']}/{model['id']}"
            self.model_box.addItem(key, key)
        index = self.model_box.findData(current)
        if index >= 0:
            self.model_box.setCurrentIndex(index)

    def add_message(self, role, text):
        self.records.append({'role': role, 'text': text})
        self.records = self.records[-150:]
        self.dirty = True

    def update_assistant(self, text):
        for record in reversed(self.records):
            if record['role'] == 'assistant':
                record['text'] = text
                self.dirty = True
                return
        self.add_message('assistant', text)

    def restore_history(self, messages):
        self.records = []
        self.tools.clear()
        if messages:
            self.add_message('notice', '已从 pi 恢复此项目的会话。以下为历史对话；右侧仅显示本次连接的工具事件。')
        for message in messages[-150:]:
            if message.get('role') in ('user', 'assistant'):
                text = message_text(message)
                if text:
                    self.add_message(message['role'], text)
        self.dirty = True

    def add_evidence(self, text):
        self.tools.addItem(text)
        while self.tools.count() > 300:
            self.tools.takeItem(0)
        self.tools.scrollToBottom()

    def render_if_dirty(self):
        if not self.dirty:
            return
        self.dirty = False
        scroll = self.transcript.verticalScrollBar()
        follow = scroll.value() >= scroll.maximum() - 30
        old = scroll.value()
        fragments = []
        names = {'user': self.controller.settings['pet']['user_name'], 'assistant': self.controller.settings['pet']['name'], 'notice': '系统'}
        for record in self.records:
            role = record['role']
            color = '#5B7867' if role == 'user' else '#876B50' if role == 'notice' else '#243C30'
            text = record['text'] or ('正在等待模型输出…' if self.is_busy else '（此轮没有文本输出）')
            fragments.append(f'<p style="color:{color}; margin-top:18px"><b>{html.escape(names[role])}</b></p><p style="white-space:pre-wrap; line-height:150%; color:{color}">{html.escape(text).replace(chr(10), "<br>")}</p>')
        self.transcript.setHtml(''.join(fragments))
        scroll.setValue(scroll.maximum() if follow else old)

    def edit_profile(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('宠物档案')
        form = QFormLayout(dialog)
        name = QLineEdit(self.controller.settings['pet']['name'])
        user_name = QLineEdit(self.controller.settings['pet']['user_name'])
        name.setMaxLength(32)
        user_name.setMaxLength(32)
        form.addRow('宠物名字', name)
        form.addRow('如何称呼你', user_name)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.controller.settings['pet'] = {'name': name.text().strip() or '华小牛', 'user_name': user_name.text().strip() or '同学'}
            self.controller.save()
            self.title.setText(f"{self.controller.settings['pet']['name']} / 项目陪伴工作台")
            self.profile_changed.emit(self.controller.settings['pet']['name'])
            self.dirty = True

    def show_model_help(self):
        box = QMessageBox(self)
        box.setWindowTitle('Anthropic 本机配置')
        box.setText('在项目目录打开 PowerShell，运行下方命令。然后在 pi 中输入 /login 并选择 Anthropic。\n\n登录完成后退出终端，回到华小牛点击“重连”。如使用环境变量，设置 ANTHROPIC_API_KEY 后需重新启动华小牛。\n\n不要把密钥粘贴到聊天里。供应商认证由 pi 管理，华小牛设置文件不保存密钥。')
        data_dir = str(self.controller.store.directory).replace("'", "''")
        login_command = (
            f"$env:PI_CODING_AGENT_DIR = '{data_dir}\\pi'\n"
            "$env:PI_TELEMETRY = '0'\n"
            "Remove-Item Env:NODE_OPTIONS, Env:NODE_PATH -ErrorAction SilentlyContinue\n"
            "node node_modules/@earendil-works/pi-coding-agent/dist/cli.js "
            "--offline --no-approve --no-extensions --no-mcp --no-skills "
            "--no-context-files --no-prompt-templates --no-themes --no-tools --no-session"
        )
        box.setInformativeText(login_command + f"\n\n本应用独立 pi 配置目录：\n{self.controller.store.pi_dir}")
        box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        open_dir = box.addButton('打开配置目录', QMessageBox.ButtonRole.ActionRole)
        reset_model = box.addButton('恢复默认模型并重连', QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if box.clickedButton() == open_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.controller.store.pi_dir)))
        elif box.clickedButton() == reset_model:
            self.controller.reset_model()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
