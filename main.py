import sys
import os
import random
import winreg
from PyQt6.QtWidgets import (
    QApplication, QWidget, QSystemTrayIcon, QMenu, QDialog,
    QVBoxLayout, QLabel, QPushButton, QCheckBox
)
from PyQt6.QtGui import QIcon, QPixmap, QAction, QActionGroup
from PyQt6.QtCore import Qt, QTimer, QPoint

# Application Constants
APP_NAME = "Bug Dance"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

class BugWidget(QWidget):
    """Floating transparent widget representing an animated bug."""
    def __init__(self, image_path, speed_factor=1.0, size_factor=1.0, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.original_pixmap = QPixmap(image_path)
        self.size_factor = size_factor
        self.speed_factor = speed_factor

        self.label = QLabel(self)
        self.update_size()

        # Initial position & random direction vector
        screen = QApplication.primaryScreen().geometry()
        self.x_pos = random.randint(100, max(200, screen.width() - 200))
        self.y_pos = random.randint(100, max(200, screen.height() - 200))
        self.move(int(self.x_pos), int(self.y_pos))

        angle_x = random.choice([-1, 1]) * random.uniform(1.5, 3.5)
        angle_y = random.choice([-1, 1]) * random.uniform(1.5, 3.5)
        self.dx = angle_x
        self.dy = angle_y

    def update_size(self):
        if self.original_pixmap.isNull():
            return
        base_width = 80
        target_width = int(base_width * self.size_factor)
        scaled = self.original_pixmap.scaledToWidth(
            target_width, Qt.TransformationMode.SmoothTransformation
        )
        self.label.setPixmap(scaled)
        self.resize(scaled.size())

    def set_size_factor(self, factor):
        self.size_factor = factor
        self.update_size()

    def set_speed_factor(self, factor):
        self.speed_factor = factor

    def step(self):
        screen = QApplication.primaryScreen().geometry()
        self.x_pos += self.dx * self.speed_factor
        self.y_pos += self.dy * self.speed_factor

        # Bounce off screen boundaries
        if self.x_pos <= 0 or self.x_pos + self.width() >= screen.width():
            self.dx *= -1
            self.x_pos = max(0, min(self.x_pos, screen.width() - self.width()))

        if self.y_pos <= 0 or self.y_pos + self.height() >= screen.height():
            self.dy *= -1
            self.y_pos = max(0, min(self.y_pos, screen.height() - self.height()))

        self.move(int(self.x_pos), int(self.y_pos))


class AboutDialog(QDialog):
    """About Dialog containing copyright and metadata."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Bug Dance")
        self.setFixedSize(320, 260)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        about_text = (
            "<b>BUG DANCE by JXD VibeLabs</b><br><br>"
            "Stoned penguin is watching you!<br>"
            "Photo © Jaroslav M. Soukup<br>"
            "Software © Jiri X. Dolezal<br>"
            "Questions: <a href='mailto:jxd@jxd.cz'>jxd@jxd.cz</a><br>"
            "<a href='https://jxd.cz/'>https://jxd.cz/</a><br><br>"
            "<i>VIBE coding is poetry.<br>"
            "Fear the penguin!</i>"
        )

        label = QLabel(about_text, self)
        label.setOpenExternalLinks(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        close_btn = QPushButton("CLOSE", self)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class BugDanceApp:
    def __init__(self, app_instance):
        self.app = app_instance
        self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        self.is_paused = False
        self.current_speed = 1.0
        self.current_size = 1.0
        self.active_bugs = {}  # index -> BugWidget

        # Load available bug images
        self.bug_images = {}
        for i in range(1, 23):
            filename = f"Jaroslav.M.Soukup_bugs_{i}.png"
            path = os.path.join(self.base_dir, filename)
            self.bug_images[i] = path

        # Tray Icon Setup
        self.tray_icon = QSystemTrayIcon()
        icon_path = os.path.join(self.base_dir, "Bug_Dance.ico")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            # Fallback standard icon if .ico missing
            self.tray_icon.setIcon(self.app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        self.tray_icon.setToolTip("Bug Dance")
        self.build_menu()
        self.tray_icon.show()

        # Initialize bugs (all checked by default)
        for i in range(1, 23):
            self.toggle_bug(i, True)

        # Animation Timer (approx ~60 FPS)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_bugs)
        self.timer.start(16)

    def build_menu(self):
        self.menu = QMenu()

        # Pause / Play Action
        self.pause_action = QAction("Pause", self.menu)
        self.pause_action.triggered.connect(self.toggle_pause)
        self.menu.addAction(self.pause_action)

        self.menu.addSeparator()

        # Speed Submenu (5 Options)
        speed_menu = self.menu.addMenu("Speed")
        speed_group = QActionGroup(self.menu)
        speed_options = [("Very Slow", 0.3), ("Slow", 0.6), ("Normal", 1.0), ("Fast", 1.8), ("Very Fast", 3.0)]
        for label, factor in speed_options:
            act = QAction(label, speed_menu, checkable=True)
            if factor == 1.0:
                act.setChecked(True)
            act.triggered.connect(lambda checked, f=factor: self.set_speed(f))
            speed_group.addAction(act)
            speed_menu.addAction(act)

        # Size Submenu (3 Options)
        size_menu = self.menu.addMenu("Size")
        size_group = QActionGroup(self.menu)
        size_options = [("Small", 0.6), ("Medium", 1.0), ("Large", 1.6)]
        for label, factor in size_options:
            act = QAction(label, size_menu, checkable=True)
            if factor == 1.0:
                act.setChecked(True)
            act.triggered.connect(lambda checked, f=factor: self.set_size(f))
            size_group.addAction(act)
            size_menu.addAction(act)

        # Bugs Submenu (Checkboxes)
        bugs_menu = self.menu.addMenu("Bugs")
        for i in range(1, 23):
            filename = f"Jaroslav.M.Soukup_bugs_{i}.png"
            act = QAction(f"Bug #{i} ({filename})", bugs_menu, checkable=True)
            act.setChecked(True)
            act.triggered.connect(lambda checked, idx=i: self.toggle_bug(idx, checked))
            bugs_menu.addAction(act)

        self.menu.addSeparator()

        # About Action
        about_action = QAction("About", self.menu)
        about_action.triggered.connect(self.show_about)
        self.menu.addAction(about_action)

        # Run at Windows start-up Action
        self.startup_action = QAction("Run at Windows start-up", self.menu, checkable=True)
        self.startup_action.setChecked(self.is_startup_enabled())
        self.startup_action.triggered.connect(self.toggle_startup)
        self.menu.addAction(self.startup_action)

        self.menu.addSeparator()

        # Exit Action
        exit_action = QAction("Exit", self.menu)
        exit_action.triggered.connect(self.exit_app)
        self.menu.addAction(exit_action)

        self.tray_icon.setContextMenu(self.menu)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.pause_action.setText("Play" if self.is_paused else "Pause")

    def set_speed(self, factor):
        self.current_speed = factor
        for bug in self.active_bugs.values():
            bug.set_speed_factor(factor)

    def set_size(self, factor):
        self.current_size = factor
        for bug in self.active_bugs.values():
            bug.set_size_factor(factor)

    def toggle_bug(self, index, enable):
        if enable:
            if index not in self.active_bugs:
                img_path = self.bug_images[index]
                if os.path.exists(img_path):
                    bug = BugWidget(img_path, self.current_speed, self.current_size)
                    bug.show()
                    self.active_bugs[index] = bug
        else:
            if index in self.active_bugs:
                bug = self.active_bugs.pop(index)
                bug.close()
                bug.deleteLater()

    def update_bugs(self):
        if self.is_paused:
            return
        for bug in self.active_bugs.values():
            bug.step()

    def show_about(self):
        dialog = AboutDialog()
        dialog.exec()

    def is_startup_enabled(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def toggle_startup(self, enable):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
            if enable:
                # Store executable path or python execution path
                if getattr(sys, 'frozen', False):
                    exe_path = f'"{sys.executable}"'
                else:
                    exe_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Error toggling startup: {e}")

    def exit_app(self):
        self.timer.stop()
        for bug in list(self.active_bugs.values()):
            bug.close()
        self.app.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    bug_dance = BugDanceApp(app)
    sys.exit(app.exec())
