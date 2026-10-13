import argparse
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox
from storage import Store
from agent.controller import Controller
from ui.pet_window import PetWindow
from ui.chat_window import ChatWindow


def main():
    parser = argparse.ArgumentParser(description='华小牛 — 基于 pi RPC 的 Python 桌宠')
    parser.add_argument('--project', help='启动后选中的本地项目目录')
    parser.add_argument('--data-dir', help='设置/会话目录，默认 LOCALAPPDATA/XiaomaoHarness')
    parser.add_argument('--pet-only', action='store_true', help='启动时仅显示桌宠')
    options = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName('XiaomaoHarness')
    app.setOrganizationName('XiaomaoCourse')
    app.setQuitOnLastWindowClosed(False)
    try:
        store = Store(options.data_dir)
    except OSError:
        QMessageBox.critical(None, '无法启动华小牛', '应用数据目录无法创建。请使用 --data-dir 指定可写目录。')
        return 1
    settings = store.load()
    controller = Controller(store, settings)
    pet = PetWindow(settings['pet']['name'], settings['topmost'])
    chat = ChatWindow(controller)
    screen = app.primaryScreen().availableGeometry()
    pet.move(screen.right() - pet.width() - 34, screen.bottom() - pet.height() - 28)
    chat.move(screen.center() - chat.rect().center())

    def show_chat():
        chat.showNormal()
        chat.raise_()
        chat.activateWindow()

    def profile_name(name):
        pet.pet_name = name
        pet.setWindowTitle(name)
        pet.update()

    def save_topmost(enabled):
        settings['topmost'] = enabled
        controller.save()

    pet.chat_requested.connect(show_chat)
    pet.topmost_changed.connect(save_topmost)
    chat.profile_changed.connect(profile_name)
    controller.status.connect(pet.set_status)
    pet.show()
    if not options.pet_only:
        show_chat()
    if store.warning:
        chat.add_message('notice', store.warning)
    project = options.project or settings.get('project')
    if project:
        chat.project_label.setText(project)
        QTimer.singleShot(0, lambda: controller.connect_project(project))

    # Keep Qt running while graceful child shutdown completes; no waitForFinished on UI thread.
    original_quit = app.quit
    closing = False

    def quit_safely():
        nonlocal closing
        if closing:
            return
        closing = True
        pet.hide()
        chat.hide()
        controller.client.exited.connect(original_quit)
        controller.shutdown()
        if not controller.client.running:
            original_quit()

    pet.quit_requested.connect(quit_safely)
    app.aboutToQuit.connect(controller.shutdown)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
