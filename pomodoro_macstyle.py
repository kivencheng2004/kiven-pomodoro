import sys
from PyQt5.QtCore import Qt, QTimer, QPoint, QObject, QEvent
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QDialog,
    QFormLayout,
    QSpinBox,
    QLineEdit,
    QDialogButtonBox,
)
from PyQt5.QtGui import QFont, QIcon, QPixmap


class SettingsDialog(QDialog):
    """设置对话框：修改任务与各阶段时长"""

    def __init__(
        self,
        parent=None,
        current_task="专注 · Deep Work",
        focus_minutes=25,
        short_minutes=5,
        long_minutes=15,
    ):
        super().__init__(parent)
        self.setWindowTitle("番茄钟设置")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QFormLayout(self)

        # 当前任务
        self.task_edit = QLineEdit(self)
        self.task_edit.setText(current_task)
        self.task_edit.setPlaceholderText("例如：操作系统作业 / 密码学论文 / 阅读…")
        layout.addRow("当前任务：", self.task_edit)

        # 专注时间
        self.focus_spin = QSpinBox(self)
        self.focus_spin.setRange(1, 180)
        self.focus_spin.setValue(focus_minutes)
        layout.addRow("专注时长（分钟）：", self.focus_spin)

        # 短休息
        self.short_spin = QSpinBox(self)
        self.short_spin.setRange(1, 60)
        self.short_spin.setValue(short_minutes)
        layout.addRow("短休息时长（分钟）：", self.short_spin)

        # 长休息
        self.long_spin = QSpinBox(self)
        self.long_spin.setRange(1, 120)
        self.long_spin.setValue(long_minutes)
        layout.addRow("长休息时长（分钟）：", self.long_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_values(self):
        task = self.task_edit.text().strip()
        if not task:
            task = "专注 · Deep Work"
        return (
            task,
            self.focus_spin.value(),
            self.short_spin.value(),
            self.long_spin.value(),
        )


class TitleBarEventFilter(QObject):
    """让顶部假标题栏可以拖动窗口"""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.drag_pos = QPoint()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.window.frameGeometry().topLeft()
            return True
        elif event.type() == QEvent.MouseMove and event.buttons() & Qt.LeftButton:
            self.window.move(event.globalPos() - self.drag_pos)
            return True
        return False


class PomodoroWindow(QWidget):
    """主窗口：Mac 风格自定义标题栏 + 白底黑字番茄钟"""

    def __init__(self):
        super().__init__()

        # 基本配置
        self.focus_minutes = 25
        self.short_break_minutes = 5
        self.long_break_minutes = 15
        self.long_break_interval = 4  # 每 4 个番茄后长休息

        self.current_mode = "focus"  # focus / short / long
        self.completed_pomodoros = 0
        self.remaining_seconds = self.focus_minutes * 60
        self.running = False

        self.current_task = "专注 · Deep Work"

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)

        # 无边框 + 始终置顶
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )

        # 应用图标（你放一个 tomato.ico 在同目录）
        self.setWindowIcon(QIcon("tomato.ico"))

        self._init_ui()

    # ========== UI ==========

    def _init_ui(self):
        self.setObjectName("rootWindow")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ==== 顶部 Mac 风标题栏 ====
        self.title_bar = QWidget(self)
        self.title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(10, 6, 10, 6)
        title_layout.setSpacing(8)

        # 四个小点：关闭 / 最小化 / 最大化 / 设置
        self.btn_close = QPushButton(self.title_bar)
        self.btn_min = QPushButton(self.title_bar)
        self.btn_max = QPushButton(self.title_bar)
        self.btn_settings_dot = QPushButton(self.title_bar)

        for b in (self.btn_close, self.btn_min, self.btn_max, self.btn_settings_dot):
            b.setFixedSize(12, 12)
            b.setFlat(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)

        self.btn_close.setObjectName("btnClose")
        self.btn_min.setObjectName("btnMin")
        self.btn_max.setObjectName("btnMax")
        self.btn_settings_dot.setObjectName("btnSettingsDot")

        dots_layout = QHBoxLayout()
        dots_layout.setContentsMargins(0, 0, 0, 0)
        dots_layout.setSpacing(6)
        dots_layout.addWidget(self.btn_close)
        dots_layout.addWidget(self.btn_min)
        dots_layout.addWidget(self.btn_max)
        dots_layout.addWidget(self.btn_settings_dot)

        dots_container = QWidget(self.title_bar)
        dots_container.setLayout(dots_layout)

        # 应用图标 + 文本 “番茄时钟 · 今日 X 个”
        self.icon_label = QLabel(self.title_bar)
        self.icon_label.setFixedSize(16, 16)
        pix = QPixmap("tomato.ico")
        if pix.isNull():
            # 如果没加载到 ico，就忽略，不报错
            pass
        else:
            self.icon_label.setPixmap(pix.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        self.title_label = QLabel(self.title_bar)
        self.title_label.setObjectName("titleLabel")
        self._update_title_label()

        title_layout.addWidget(dots_container)
        title_layout.addSpacing(6)
        title_layout.addWidget(self.icon_label)
        title_layout.addSpacing(6)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch(1)

        root_layout.addWidget(self.title_bar)

        # ==== 中心内容 ====
        central = QWidget(self)
        central.setObjectName("centralArea")
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(16, 12, 16, 16)
        central_layout.setSpacing(12)

        self.task_label = QLabel(self.current_task, central)
        self.task_label.setAlignment(Qt.AlignCenter)

        self.time_label = QLabel(central)
        self.time_label.setAlignment(Qt.AlignCenter)

        self.state_label = QLabel(central)
        self.state_label.setAlignment(Qt.AlignCenter)

        central_layout.addStretch(1)
        central_layout.addWidget(self.task_label)
        central_layout.addWidget(self.time_label)
        central_layout.addWidget(self.state_label)
        central_layout.addStretch(1)

        root_layout.addWidget(central)

        # ==== 样式 ====
        self.setStyleSheet(
            """
            #rootWindow {
                background-color: #FFFFFF;
                border: 1px solid #DDDDDD;
                border-radius: 8px;
            }
            #titleBar {
                background-color: #F5F5F5;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            #centralArea {
                background-color: #FFFFFF;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            #titleLabel {
                color: #555555;
                font-family: "Segoe UI", system-ui;
                font-size: 9pt;
            }
            QLabel {
                color: #111111;
                font-family: "Segoe UI", system-ui;
            }
            QLabel#stateLabel {
                color: #444444;
            }
            QPushButton#btnClose {
                background-color: #ff5f57;
                border-radius: 6px;
                border: none;
            }
            QPushButton#btnClose:hover {
                background-color: #ff615a;
            }
            QPushButton#btnMin {
                background-color: #febc2e;
                border-radius: 6px;
                border: none;
            }
            QPushButton#btnMin:hover {
                background-color: #fec23a;
            }
            QPushButton#btnMax {
                background-color: #28c840;
                border-radius: 6px;
                border: none;
            }
            QPushButton#btnMax:hover {
                background-color: #2bd347;
            }
            QPushButton#btnSettingsDot {
                background-color: #C4C4C4;
                border-radius: 6px;
                border: none;
            }
            QPushButton#btnSettingsDot:hover {
                background-color: #AFAFAF;
            }
            """
        )

        # 字体
        title_font = QFont("Segoe UI", 11)
        title_font.setBold(True)
        self.task_label.setFont(title_font)

        time_font = QFont("Consolas", 34)
        time_font.setBold(True)
        self.time_label.setFont(time_font)

        state_font = QFont("Segoe UI", 10)
        self.state_label.setFont(state_font)

        # 初始状态
        self.resize(420, 220)
        self._update_time_label()
        self._update_state_label()

        # 绑定按钮行为
        self.btn_close.clicked.connect(self.close)
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_max.clicked.connect(self._toggle_max_restore)
        self.btn_settings_dot.clicked.connect(self.open_settings)

        # time_label 单击 = 开始/暂停
        self.time_label.installEventFilter(self)

        # 顶部标题栏可拖动
        self.title_bar_filter = TitleBarEventFilter(self)
        self.title_bar.installEventFilter(self.title_bar_filter)

    # ========== 计时与状态 ==========

    def _update_title_label(self):
        self.title_label.setText(f"番茄时钟 · 今日 {self.completed_pomodoros} 个")

    def _update_time_label(self):
        m = self.remaining_seconds // 60
        s = self.remaining_seconds % 60
        self.time_label.setText(f"{m:02d}:{s:02d}")

    def _update_state_label(self):
        mode_text = {
            "focus": "专注",
            "short": "短休息",
            "long": "长休息",
        }.get(self.current_mode, "专注")

        if self.running:
            self.state_label.setText(f"状态：{mode_text}中（点击时间暂停）")
        else:
            self.state_label.setText(f"状态：{mode_text}（点击时间开始）")

    def _duration_for_mode(self, mode: str) -> int:
        if mode == "focus":
            return self.focus_minutes * 60
        elif mode == "short":
            return self.short_break_minutes * 60
        elif mode == "long":
            return self.long_break_minutes * 60
        return self.focus_minutes * 60

    def _on_tick(self):
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self._update_time_label()
        else:
            # 当前阶段结束
            self.timer.stop()
            self.running = False
            QApplication.beep()

            if self.current_mode == "focus":
                self.completed_pomodoros += 1
                self._update_title_label()

                # 决定是长休还是短休
                if self.completed_pomodoros % self.long_break_interval == 0:
                    self.current_mode = "long"
                else:
                    self.current_mode = "short"
            else:
                self.current_mode = "focus"

            self.remaining_seconds = self._duration_for_mode(self.current_mode)
            self._update_time_label()
            self._update_state_label()

    def toggle_running(self):
        if self.running:
            self.timer.stop()
            self.running = False
        else:
            if self.remaining_seconds <= 0:
                self.remaining_seconds = self._duration_for_mode(self.current_mode)
                self._update_time_label()
            self.timer.start(1000)
            self.running = True
        self._update_state_label()

    # ========== 设置对话框 ==========

    def open_settings(self):
        dlg = SettingsDialog(
            self,
            current_task=self.current_task,
            focus_minutes=self.focus_minutes,
            short_minutes=self.short_break_minutes,
            long_minutes=self.long_break_minutes,
        )
        if dlg.exec_() == QDialog.Accepted:
            task, focus_m, short_m, long_m = dlg.get_values()
            self.current_task = task
            self.focus_minutes = focus_m
            self.short_break_minutes = short_m
            self.long_break_minutes = long_m

            self.task_label.setText(self.current_task)

            if not self.running:
                self.remaining_seconds = self._duration_for_mode(self.current_mode)
                self._update_time_label()
            self._update_state_label()

    # ========== 事件处理 ==========

    def eventFilter(self, obj, event):
        # 点击时间 = 开始/暂停
        if obj is self.time_label and event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                self.toggle_running()
                return True
        return super().eventFilter(obj, event)

    def _toggle_max_restore(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("番茄时钟")

    base_font = QFont("Segoe UI", 9)
    app.setFont(base_font)

    w = PomodoroWindow()
    w.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
