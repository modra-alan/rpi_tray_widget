#!/usr/bin/env python3
import sys, subprocess, shlex, functools
from PyQt5 import QtWidgets, QtGui, QtCore

SERVICE = sys.argv[1] if len(sys.argv) > 1 else "creelmt-winder-display.service"
CHECK_INTERVAL_MS = 3000  # poll status every 3s

GREEN_SVG = b"""<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16'>
<circle cx='8' cy='8' r='7' fill='#3cb371' stroke='#0a0' stroke-width='1'/></svg>"""
RED_SVG = b"""<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16'>
<circle cx='8' cy='8' r='7' fill='#ff6b6b' stroke='#900' stroke-width='1'/></svg>"""


def svg_icon(svg_bytes: bytes) -> QtGui.QIcon:
    img = QtGui.QImage.fromData(svg_bytes, "SVG")
    pm = QtGui.QPixmap.fromImage(img)
    return QtGui.QIcon(pm)


def run(cmd: str) -> subprocess.CompletedProcess:
    # use sudo for allowed commands; stderr captured for messages
    return subprocess.run(
        shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )


def systemctl(*args: str) -> subprocess.CompletedProcess:
    return run("systemctl --user" + " ".join(shlex.quote(a) for a in args))


class ServiceTray(QtWidgets.QSystemTrayIcon):
    def __init__(self, service: str, parent=None):
        super().__init__(parent)
        self.service = service

        # icons
        self.icon_on = svg_icon(GREEN_SVG)
        self.icon_off = svg_icon(RED_SVG)
        self.setToolTip(f"{self.service}: checking…")
        self.setIcon(self.icon_off)

        # menu
        menu = QtWidgets.QMenu()
        self.action_start = menu.addAction("Start")
        self.action_stop = menu.addAction("Stop")
        self.action_restart = menu.addAction("Restart")
        menu.addSeparator()
        self.action_enable = menu.addAction("Enable on boot")
        self.action_enable.setCheckable(True)
        menu.addSeparator()
        self.action_logs = menu.addAction("Show recent logs…")
        menu.addSeparator()
        self.action_quit = menu.addAction("Quit")

        self.setContextMenu(menu)

        # wires
        self.activated.connect(self.on_activated)
        self.action_start.triggered.connect(lambda: self.do_action("start"))
        self.action_stop.triggered.connect(lambda: self.do_action("stop"))
        self.action_restart.triggered.connect(lambda: self.do_action("restart"))
        self.action_enable.triggered.connect(self.toggle_enable)
        self.action_logs.triggered.connect(self.show_logs)
        self.action_quit.triggered.connect(QtWidgets.QApplication.quit)

        # status timer
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(CHECK_INTERVAL_MS)

        # initial
        self.refresh_status()

    def on_activated(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason):
        # left click toggles start/stop
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            # decide based on current status
            if self._active:
                self.do_action("stop")
            else:
                self.do_action("start")

    def refresh_status(self):
        active = systemctl("is-active", self.service)
        enabled = systemctl("is-enabled", self.service)

        self._active = active.stdout.strip() == "active"
        is_enabled = enabled.stdout.strip() == "enabled"

        # update icon + tooltip
        if self._active:
            self.setIcon(self.icon_on)
            self.setToolTip(f"{self.service}: active")
        else:
            self.setIcon(self.icon_off)
            self.setToolTip(f"{self.service}: inactive")

        # update menu enable/disable states
        self.action_start.setEnabled(not self._active)
        self.action_stop.setEnabled(self._active)
        self.action_restart.setEnabled(True)
        # reflect enable state
        self.action_enable.blockSignals(True)
        self.action_enable.setChecked(is_enabled)
        self.action_enable.blockSignals(False)

    def do_action(self, action: str):
        proc = systemctl(action, self.service)
        if proc.returncode != 0:
            self.notify(
                "Error", proc.stderr.strip() or f"Failed to {action} {self.service}"
            )
        self.refresh_status()

    def toggle_enable(self, checked: bool):
        proc = systemctl("enable" if checked else "disable", self.service)
        if proc.returncode != 0:
            self.notify("Error", proc.stderr.strip() or "Failed to change enable state")
            # revert checkbox to actual state
            self.refresh_status()

    def show_logs(self):
        # Grab last 100 lines and display in a simple dialog
        p = run(
            f"journalctl -u {shlex.quote(self.service)} -n 100 --no-pager --output=short"
        )
        dlg = QtWidgets.QDialog()
        dlg.setWindowTitle(f"Logs: {self.service} (last 100)")
        layout = QtWidgets.QVBoxLayout(dlg)
        text = QtWidgets.QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(p.stdout if p.stdout else p.stderr)
        layout.addWidget(text)
        btn = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btn.rejected.connect(dlg.reject)
        layout.addWidget(btn)
        dlg.resize(800, 500)
        dlg.exec_()

    def notify(self, title: str, message: str):
        self.showMessage(title, message, self.icon())


def main():
    app = QtWidgets.QApplication(sys.argv)
    tray = ServiceTray(SERVICE)
    tray.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
