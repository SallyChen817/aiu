import math
from PySide6.QtCore import QPoint, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QApplication, QMenu, QWidget


class PetWindow(QWidget):
    chat_requested = Signal()
    topmost_changed = Signal(bool)
    quit_requested = Signal()

    def __init__(self, name='华小牛', topmost=True):
        super().__init__()
        self.pet_name = name
        self.state = 'idle'
        self.progress = '双击我，聊聊你的项目'
        self.phase = 0
        self.drag_offset = None
        self.setWindowTitle(name)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.set_topmost(topmost)
        self.resize(240, 258)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(80)
        self.setToolTip('拖动移动 · 双击聊天 · 右键菜单')

    def set_topmost(self, enabled):
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        if visible:
            self.show()

    def set_status(self, state, progress):
        self.state, self.progress = state, progress
        self.update()

    def tick(self):
        self.phase += 0.22
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = {'idle': '#627C72', 'thinking': '#A075D5', 'working': '#D59A42', 'done': '#48A383', 'error': '#C96E72'}
        accent = QColor(palette[self.state])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(34, 42, 47, 235))
        painter.drawRoundedRect(8, 5, 224, 49, 16, 16)
        painter.setPen(QColor('#F9F5EB'))
        painter.drawText(18, 9, 204, 41, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.progress[:48])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 24))
        painter.drawEllipse(53, 216, 138, 18)
        bob = math.sin(self.phase) * (5 if self.state in ('working', 'done') else 2)
        painter.translate(0, bob)
        painter.setPen(QPen(QColor('#464C47'), 3))
        painter.setBrush(QColor('#F7EFDC'))
        painter.drawRoundedRect(64, 141, 112, 78, 37, 37)
        painter.setBrush(QColor('#8C7365'))
        painter.drawEllipse(73, 176, 31, 31)
        painter.setBrush(QColor('#E8D5AE'))
        painter.drawPolygon(QPolygonF([QPointF(79, 97), QPointF(73, 66), QPointF(98, 91)]))
        painter.drawPolygon(QPolygonF([QPointF(143, 91), QPointF(166, 66), QPointF(160, 99)]))
        painter.setBrush(QColor('#F7EFDC'))
        painter.drawEllipse(38, 98, 47, 25)
        painter.drawEllipse(157, 98, 47, 25)
        painter.drawRoundedRect(61, 87, 119, 95, 39, 39)
        painter.setBrush(QColor('#8C7365'))
        painter.drawEllipse(72, 99, 35, 37)
        painter.setPen(QPen(QColor('#343B37'), 4))
        if self.state == 'done':
            painter.drawArc(83, 119, 18, 14, 0, 180 * 16)
            painter.drawArc(140, 119, 18, 14, 0, 180 * 16)
        else:
            painter.drawPoint(93, 125)
            painter.drawPoint(148, 125)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#E9B3A3'))
        painter.drawRoundedRect(89, 140, 66, 32, 15, 15)
        painter.setBrush(QColor('#845F57'))
        painter.drawEllipse(104, 150, 4, 5)
        painter.drawEllipse(137, 150, 4, 5)
        painter.setBrush(accent)
        painter.drawRoundedRect(80, 179, 81, 12, 6, 6)
        painter.setBrush(QColor('#F4CE6C'))
        painter.drawEllipse(112, 185, 16, 17)
        if self.state == 'thinking':
            painter.setPen(QPen(accent, 4))
            painter.drawArc(188, 67, 23, 23, int(self.phase * 100) * 16, 220 * 16)
        if self.state == 'error':
            painter.setPen(QPen(accent, 4))
            painter.drawText(193, 90, '!')
        painter.resetTransform()
        painter.setPen(QColor('#39463F'))
        painter.drawText(0, 237, 240, 20, Qt.AlignmentFlag.AlignCenter, self.pet_name)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_offset)

    def mouseReleaseEvent(self, event):
        self.drag_offset = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.chat_requested.emit()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction('打开聊天', self.chat_requested.emit)
        top = menu.addAction('总在最前')
        top.setCheckable(True)
        top.setChecked(bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint))
        top.toggled.connect(self.set_topmost)
        top.toggled.connect(self.topmost_changed.emit)
        menu.addSeparator()
        menu.addAction('退出华小牛', self.quit_requested.emit)
        menu.exec(event.globalPos())
