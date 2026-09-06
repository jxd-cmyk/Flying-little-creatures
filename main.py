"""
Bug Dance — cross-platform desktop pet (Windows / macOS / Linux)
Requires: PyQt6 ≥ 6.5  *or*  PySide6 ≥ 6.5
"""

import sys
import os
import random
import shlex                              # needed for Linux .desktop Exec quoting
import xml.sax.saxutils as _xmlesc        # for safe plist generation

# ---------------------------------------------------------------------------
# Try PyQt6 first, fall back to PySide6 — fail loudly if neither is present
# ---------------------------------------------------------------------------
try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QSystemTrayIcon, QMenu, QDialog,
        QVBoxLayout, QLabel, QPushButton, QStyle, QMessageBox,
    )
    from PyQt6.QtGui import QIcon, QPixmap, QAction, QActionGroup
    from PyQt6.QtCore import Qt, QTimer, QRect
    _QT_BINDING = "PyQt6"
except ImportError:
    try:
        from PySide6.QtWidgets import (
            QApplication, QWidget, QSystemTrayIcon, QMenu, QDialog,
            QVBoxLayout, QLabel, QPushButton, QStyle, QMessageBox,
        )
        from PySide6.QtGui import QIcon, QPixmap, QAction, QActionGroup
        from PySide6.QtCore import Qt, QTimer, QRect
        _QT_BINDING = "PySide6"
    except ImportError:
        sys.exit(
            "ERROR: Neither PyQt6 nor PySide6 is installed.\n"
            "Install one of them:  pip install PyQt6\n"
        )

# ---------------------------------------------------------------------------
# Windows-only: registry for startup management
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    import winreg

# ---------------------------------------------------------------------------
# macOS: suppress Dock icon (requires pyobjc — optional, silently skipped)
# ---------------------------------------------------------------------------
if sys.platform == "darwin":
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyAccessory
        )
    except Exception:
        pass  # pyobjc not installed — Dock icon will appear, non-fatal

# ---------------------------------------------------------------------------
# Application constants
# ---------------------------------------------------------------------------
APP_NAME = "Bug Dance"
APP_ORG  = "JXD VibeLabs"
APP_ID   = "cz.jxd.BugDance"        # reverse-DNS id for macOS plist / Linux desktop
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

# WindowTransparentForInput is only meaningful (and click-through) on Windows.
# On X11/Wayland the Qt enum value exists but the compositor ignores it and
# the window still captures mouse events — so we restrict it to win32 only.
_USE_TRANSPARENT_INPUT = sys.platform == "win32"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_dir() -> str:
    """
    Return the directory that contains the script / frozen executable.
    Works correctly when:
      - run as `python main.py`
      - run as a PyInstaller / cx_Freeze executable
      - imported as a module
    """
    if getattr(sys, "frozen", False):
        # PyInstaller sets sys.executable to the packaged binary
        return os.path.dirname(os.path.abspath(sys.executable))
    # __file__ is always reliable; avoids sys.argv[0] pitfalls
    return os.path.dirname(os.path.abspath(__file__))


def _get_screen_geometry() -> QRect:
    """Return primary-screen geometry, falling back to 1920×1080 if unavailable."""
    screen = QApplication.primaryScreen()
    if screen is not None:
        return screen.geometry()
    return QRect(0, 0, 1920, 1080)


def _make_app_icon(base_dir: str) -> QIcon:
    """
    Load the tray icon from disk.
    Priority: Bug_Dance.ico → Bug_Dance.png → first bug image → Qt built-in fallback
    """
    for candidate in (
        os.path.join(base_dir, "Bug_Dance.ico"),
        os.path.join(base_dir, "Bug_Dance.png"),
        os.path.join(base_dir, "Jaroslav.M.Soukup_bugs_1.png"),
    ):
        if os.path.exists(candidate):
            icon = QIcon(candidate)
            if not icon.isNull():
                return icon
    # Last-resort: built-in Qt icon (always works)
    return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)


def _executable_args() -> "tuple[str, list[str]]":
    """Return (program, [args]) suitable for a startup entry on any platform."""
    if getattr(sys, "frozen", False):
        return sys.executable, []
    return sys.executable, [os.path.abspath(__file__)]


# ---------------------------------------------------------------------------
# BugWidget
# ---------------------------------------------------------------------------

class BugWidget(QWidget):
    """Floating transparent widget representing an animated bug."""

    def __init__(self, image_path: str, speed_factor: float = 1.0,
                 size_factor: float = 1.0, parent=None):
        super().__init__(parent)

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        # Only enable click-through on Windows where it actually works
        if _USE_TRANSPARENT_INPUT:
            flags |= Qt.WindowType.WindowTransparentForInput

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.original_pixmap = QPixmap(image_path)
        self.size_factor = size_factor
        self.speed_factor = speed_factor

        self.label = QLabel(self)
        self.update_size()   # sets real widget dimensions

        # Place bug after update_size() so width()/height() are already valid
        geo = _get_screen_geometry()
        w, h = max(1, self.width()), max(1, self.height())
        self.x_pos = float(random.randint(0, max(0, geo.width() - w)))
        self.y_pos = float(random.randint(0, max(0, geo.height() - h)))
        self.move(int(self.x_pos), int(self.y_pos))

        self.dx = random.choice([-1, 1]) * random.uniform(1.5, 3.5)
        self.dy = random.choice([-1, 1]) * random.uniform(1.5, 3.5)

    # ------------------------------------------------------------------
    def update_size(self):
        if self.original_pixmap.isNull():
            return
        target_width = max(1, int(80 * self.size_factor))
        scaled = self.original_pixmap.scaledToWidth(
            target_width, Qt.TransformationMode.SmoothTransformation
        )
        self.label.setPixmap(scaled)
        self.resize(scaled.size())

    def set_size_factor(self, factor: float):
        self.size_factor = factor
        self.update_size()

    def set_speed_factor(self, factor: float):
        self.speed_factor = factor

    def step(self, geo: QRect):
        """Advance the bug by one frame. Caller supplies pre-fetched geometry."""
        self.x_pos += self.dx * self.speed_factor
        self.y_pos += self.dy * self.speed_factor

        w = max(1, self.width())
        h = max(1, self.height())
        sw = geo.width()
        sh = geo.height()

        if self.x_pos <= 0 or self.x_pos + w >= sw:
            self.dx *= -1
            self.x_pos = max(0.0, min(self.x_pos, float(sw - w)))

        if self.y_pos <= 0 or self.y_pos + h >= sh:
            self.dy *= -1
            self.y_pos = max(0.0, min(self.y_pos, float(sh - h)))

        self.move(int(self.x_pos), int(self.y_pos))


# ---------------------------------------------------------------------------
# AboutDialog
# ---------------------------------------------------------------------------

class AboutDialog(QDialog):
    """About Dialog containing copyright and metadata."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Bug Dance")
        self.setFixedSize(320, 280)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

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
            f"<small>Running on {_QT_BINDING} · {sys.platform}</small><br><br>"
            "<i>VIBE coding is poetry.<br>Fear the penguin!</i>"
        )

        label = QLabel(about_text, self)
        label.setOpenExternalLinks(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        layout.addWidget(label)

        close_btn = QPushButton("CLOSE", self)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


# ---------------------------------------------------------------------------
# Cross-platform startup helpers
# ---------------------------------------------------------------------------

def _startup_label() -> str:
    if sys.platform == "win32":
        return "Run at Windows start-up"
    if sys.platform == "darwin":
        return "Run at macOS login"
    return "Run at login"


# --- Windows (registry) ---

def _is_startup_enabled_win() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)   # always closed, even on exception
    except Exception:
        return False


def _toggle_startup_win(enable: bool):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        try:
            if enable:
                prog, args = _executable_args()
                parts = [f'"{prog}"'] + [f'"{a}"' for a in args]
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, " ".join(parts))
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)   # always closed, even on exception
    except Exception as exc:
        print(f"[BugDance] Error toggling startup (win): {exc}", file=sys.stderr)


# --- macOS (launchd plist) ---

def _plist_path() -> str:
    return os.path.join(
        os.path.expanduser("~/Library/LaunchAgents"),
        f"{APP_ID}.plist",
    )


def _is_startup_enabled_mac() -> bool:
    return os.path.exists(_plist_path())


def _toggle_startup_mac(enable: bool):
    plist = _plist_path()
    if enable:
        # Only create the directory when actually writing the file
        os.makedirs(os.path.dirname(plist), exist_ok=True)
        prog, args = _executable_args()
        all_args = [prog] + args
        args_xml = "\n        ".join(
            f"<string>{_xmlesc.escape(a)}</string>" for a in all_args
        )
        content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"\n'
            ' "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n<dict>\n'
            f'    <key>Label</key>\n    <string>{_xmlesc.escape(APP_ID)}</string>\n'
            f'    <key>ProgramArguments</key>\n    <array>\n        {args_xml}\n    </array>\n'
            '    <key>RunAtLoad</key>\n    <true/>\n'
            '    <key>KeepAlive</key>\n    <false/>\n'
            '</dict>\n</plist>\n'
        )
        try:
            with open(plist, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as exc:
            print(f"[BugDance] Error creating plist: {exc}", file=sys.stderr)
    else:
        try:
            if os.path.exists(plist):
                os.remove(plist)
        except Exception as exc:
            print(f"[BugDance] Error removing plist: {exc}", file=sys.stderr)


# --- Linux (XDG autostart .desktop) ---

def _desktop_path() -> str:
    return os.path.join(
        os.path.expanduser("~/.config/autostart"),
        f"{APP_ID}.desktop",
    )


def _is_startup_enabled_linux() -> bool:
    return os.path.exists(_desktop_path())


def _toggle_startup_linux(enable: bool):
    desktop = _desktop_path()
    if enable:
        # Only create the directory when actually writing the file
        os.makedirs(os.path.dirname(desktop), exist_ok=True)
        prog, args = _executable_args()
        exec_line = shlex.join([prog] + args)   # handles spaces in paths
        content = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={APP_NAME}\n"
            f"Exec={exec_line}\n"
            "Hidden=false\n"
            "NoDisplay=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        try:
            with open(desktop, "w", encoding="utf-8") as f:
                f.write(content)
            os.chmod(desktop, 0o755)
        except Exception as exc:
            print(f"[BugDance] Error creating .desktop: {exc}", file=sys.stderr)
    else:
        try:
            if os.path.exists(desktop):
                os.remove(desktop)
        except Exception as exc:
            print(f"[BugDance] Error removing .desktop: {exc}", file=sys.stderr)


# --- Dispatch ---

def is_startup_enabled() -> bool:
    if sys.platform == "win32":
        return _is_startup_enabled_win()
    if sys.platform == "darwin":
        return _is_startup_enabled_mac()
    return _is_startup_enabled_linux()


def toggle_startup(enable: bool):
    if sys.platform == "win32":
        _toggle_startup_win(enable)
    elif sys.platform == "darwin":
        _toggle_startup_mac(enable)
    else:
        _toggle_startup_linux(enable)


# ---------------------------------------------------------------------------
# Main application class
# ---------------------------------------------------------------------------

class BugDanceApp:
    def __init__(self, app_instance: QApplication):
        self.app = app_instance
        self.base_dir = _base_dir()

        self.is_paused = False
        self.current_speed = 1.0
        self.current_size = 1.0
        self.active_bugs: "dict[int, BugWidget]" = {}

        # Map bug index → image path (only paths that actually exist on disk)
        self.bug_images: "dict[int, str]" = {}
        for i in range(1, 23):
            path = os.path.join(self.base_dir, f"Jaroslav.M.Soukup_bugs_{i}.png")
            if os.path.exists(path):
                self.bug_images[i] = path

        # System-tray icon
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(_make_app_icon(self.base_dir))
        self.tray_icon.setToolTip(APP_NAME)
        self.build_menu()
        self.tray_icon.show()

        # Spawn bugs for all images found on disk
        for i in self.bug_images:
            self.toggle_bug(i, True)

        # Cache screen geometry; refresh only when the screen configuration changes
        self._screen_geo = _get_screen_geometry()
        screen = QApplication.primaryScreen()
        if screen is not None:
            screen.geometryChanged.connect(self._on_screen_changed)

        # Animation timer (~60 FPS)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_bugs)
        self.timer.start(16)

    def _on_screen_changed(self, *_):
        """Re-cache geometry whenever the screen resolution/arrangement changes."""
        self._screen_geo = _get_screen_geometry()

    # ------------------------------------------------------------------
    def build_menu(self):
        self.menu = QMenu()

        self.pause_action = QAction("Pause", self.menu)
        self.pause_action.triggered.connect(self.toggle_pause)
        self.menu.addAction(self.pause_action)
        self.menu.addSeparator()

        # Speed sub-menu — action group is parented to the sub-menu (correct lifetime)
        speed_menu = self.menu.addMenu("Speed")
        speed_group = QActionGroup(speed_menu)
        speed_group.setExclusive(True)
        for label, factor in [
            ("Very Slow", 0.3), ("Slow", 0.6), ("Normal", 1.0),
            ("Fast", 1.8), ("Very Fast", 3.0),
        ]:
            act = QAction(label, speed_menu, checkable=True)
            act.setChecked(factor == 1.0)
            act.triggered.connect(lambda checked, f=factor: self.set_speed(f))
            speed_group.addAction(act)
            speed_menu.addAction(act)

        # Size sub-menu — action group parented to the sub-menu
        size_menu = self.menu.addMenu("Size")
        size_group = QActionGroup(size_menu)
        size_group.setExclusive(True)
        for label, factor in [("Small", 0.6), ("Medium", 1.0), ("Large", 1.6)]:
            act = QAction(label, size_menu, checkable=True)
            act.setChecked(factor == 1.0)
            act.triggered.connect(lambda checked, f=factor: self.set_size(f))
            size_group.addAction(act)
            size_menu.addAction(act)

        # Bugs sub-menu — only lists images actually present on disk
        bugs_menu = self.menu.addMenu("Bugs")
        for i, path in self.bug_images.items():
            act = QAction(f"Bug #{i} ({os.path.basename(path)})", bugs_menu, checkable=True)
            act.setChecked(True)
            act.triggered.connect(lambda checked, idx=i: self.toggle_bug(idx, checked))
            bugs_menu.addAction(act)

        self.menu.addSeparator()

        about_action = QAction("About", self.menu)
        about_action.triggered.connect(self.show_about)
        self.menu.addAction(about_action)

        self.startup_action = QAction(_startup_label(), self.menu, checkable=True)
        self.startup_action.setChecked(is_startup_enabled())
        self.startup_action.triggered.connect(self.on_toggle_startup)
        self.menu.addAction(self.startup_action)

        self.menu.addSeparator()

        exit_action = QAction("Exit", self.menu)
        exit_action.triggered.connect(self.exit_app)
        self.menu.addAction(exit_action)

        self.tray_icon.setContextMenu(self.menu)

    # ------------------------------------------------------------------
    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.pause_action.setText("Play" if self.is_paused else "Pause")

    def set_speed(self, factor: float):
        self.current_speed = factor
        for bug in self.active_bugs.values():
            bug.set_speed_factor(factor)

    def set_size(self, factor: float):
        self.current_size = factor
        for bug in self.active_bugs.values():
            bug.set_size_factor(factor)

    def toggle_bug(self, index: int, enable: bool):
        if enable:
            if index not in self.active_bugs and index in self.bug_images:
                try:
                    bug = BugWidget(
                        self.bug_images[index],
                        self.current_speed,
                        self.current_size,
                    )
                    bug.show()
                    self.active_bugs[index] = bug
                except Exception as exc:
                    print(f"[BugDance] Could not create bug #{index}: {exc}", file=sys.stderr)
        else:
            bug = self.active_bugs.pop(index, None)
            if bug is not None:
                bug.close()
                bug.deleteLater()

    def update_bugs(self):
        if self.is_paused:
            return
        # Pass the cached geometry so we don't hit the OS 60× per second
        geo = self._screen_geo
        for bug in list(self.active_bugs.values()):
            try:
                bug.step(geo)
            except Exception as exc:
                print(f"[BugDance] step() error: {exc}", file=sys.stderr)

    def show_about(self):
        # Pass a stable parent so the dialog is owned and stays on top
        dlg = AboutDialog(parent=None)
        dlg.exec()

    def on_toggle_startup(self, enable: bool):
        toggle_startup(enable)

    def exit_app(self):
        # Disconnect signal first to prevent any pending timeout from firing
        self.timer.timeout.disconnect(self.update_bugs)
        self.timer.stop()
        for bug in list(self.active_bugs.values()):
            bug.close()
            bug.deleteLater()
        self.active_bugs.clear()
        self.tray_icon.hide()
        self.app.quit()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # High-DPI support (automatic in Qt 6.x; these attrs are deprecated but harmless)
    for attr_name in ("AA_EnableHighDpiScaling", "AA_UseHighDpiPixmaps"):
        attr = getattr(Qt, attr_name, None) or getattr(Qt.ApplicationAttribute, attr_name, None)
        if attr is not None:
            QApplication.setAttribute(attr, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    app.setOrganizationDomain("jxd.cz")
    app.setQuitOnLastWindowClosed(False)

    # Abort gracefully if the desktop has no system tray (headless / bare GNOME)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(
            None,
            APP_NAME,
            "No system tray is available on this desktop.\n\n"
            "On Linux you may need a tray-support extension\n"
            "(e.g. 'AppIndicator' for GNOME).",
        )
        sys.exit(1)

    _bug_dance = BugDanceApp(app)  # noqa: F841 — kept alive by local reference
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
