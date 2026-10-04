# -*- coding: utf-8 -*-
"""SUPERGO 2.0 (Windows 7+ edition)
Flat dark browser, tabs in the sidebar. Engine: Qt5 QtWebEngine (Chromium) - NO WebView2.
Build with Python 3.8 (last Python that runs on Windows 7)."""
import os, sys, json, time, sqlite3, subprocess

import vpn

APP = "SUPERGO"
FROZEN = getattr(sys, "frozen", False)
BASE = os.path.dirname(sys.executable if FROZEN else os.path.abspath(__file__))
DATA = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP)
os.makedirs(DATA, exist_ok=True)


RES = getattr(sys, "_MEIPASS", BASE)  # where bundled files (icon) live


def P(n):
    return os.path.join(DATA, n)


def jload(n, d):
    try:
        with open(P(n), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def jsave(n, v):
    try:
        with open(P(n), "w", encoding="utf-8") as f:
            json.dump(v, f, indent=1)
    except Exception:
        pass


CFG = jload("settings.json", {})
HOME = CFG.get("home", "https://duckduckgo.com/")
SEARCH = CFG.get("search", "https://duckduckgo.com/?q=%s")
DLDIR = CFG.get("download_dir", os.path.join(os.path.expanduser("~"), "Downloads"))
VPN = jload("vpn.json", {})
PORT = int(VPN.get("port", 10808))
VPN_ON = bool(VPN.get("enabled") and VPN.get("text"))
xray, vpn_error, RESTART = None, "", False

# ---- must happen BEFORE QApplication is created ----
flags = []
if VPN_ON:
    try:
        xray = vpn.start(VPN["text"], PORT, [BASE, DATA], DATA)
    except Exception as e:
        vpn_error = str(e)
    # proxy flag is set even if the core failed -> traffic is blocked, never leaked
    flags += ["--proxy-server=socks5://127.0.0.1:%d" % PORT,
              "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"]
if os.environ.get("SUPERGO_SOFTWARE"):
    flags.append("--disable-gpu")
if flags:
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(flags)

from PyQt5.QtCore import Qt, QUrl, QTimer
from PyQt5.QtGui import QKeySequence, QDesktopServices, QIcon
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QListWidget, QListWidgetItem, QLineEdit, QLabel, QStackedWidget, QDialog,
                             QPlainTextEdit, QMessageBox, QFileDialog, QInputDialog, QMenu, QShortcut)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile

db = sqlite3.connect(P("data.db"))
db.execute("CREATE TABLE IF NOT EXISTS history(url TEXT PRIMARY KEY,title TEXT,ts REAL,visits INTEGER DEFAULT 1)")
db.execute("CREATE TABLE IF NOT EXISTS bookmarks(url TEXT PRIMARY KEY,title TEXT,ts REAL)")
db.commit()

STYLE = """
QWidget{background:#16181d;color:#d8dbe2;font-size:13px}
QLineEdit,QPlainTextEdit,QListWidget{background:#1e2128;border:1px solid #2b2f38;border-radius:4px;padding:4px}
QListWidget::item{padding:6px}QListWidget::item:selected{background:#2f3a52;color:#fff}
QPushButton{background:#232733;border:1px solid #2b2f38;border-radius:4px;padding:5px 9px}
QPushButton:hover{background:#2f3547}
QMenu{background:#1e2128;border:1px solid #2b2f38}QMenu::item:selected{background:#2f3a52}
"""


def fix_url(t):
    t = t.strip()
    if not t:
        return QUrl(HOME)
    if "://" in t or t.startswith(("about:", "file:")):
        return QUrl(t)
    if " " not in t and ("." in t or t.startswith("localhost")):
        return QUrl(("http://" if t.startswith(("localhost", "127.", "192.168.")) else "https://") + t)
    return QUrl(SEARCH % QUrl.toPercentEncoding(t).data().decode())


class View(QWebEngineView):
    def __init__(self, win, profile, private):
        super().__init__()
        self.win, self.private = win, private
        self.setPage(QWebEnginePage(profile, self))

    def createWindow(self, _kind):  # target=_blank / window.open
        return self.win.new_tab(private=self.private)


class ListDialog(QDialog):
    def __init__(self, parent, title, rows, on_open, on_delete=None, on_clear=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 480)
        self.on_open, self.on_delete = on_open, on_delete
        lay = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter...")
        self.lst = QListWidget()
        for text, url in rows:
            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, url)
            self.lst.addItem(it)
        lay.addWidget(self.search)
        lay.addWidget(self.lst)
        row = QHBoxLayout()
        if on_delete:
            b = QPushButton("Delete selected")
            b.clicked.connect(self.delete)
            row.addWidget(b)
        if on_clear:
            b = QPushButton("Clear all")
            b.clicked.connect(lambda: (on_clear(), self.lst.clear()))
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        self.lst.itemDoubleClicked.connect(lambda it: (self.on_open(it.data(Qt.UserRole)), self.accept()))
        self.search.textChanged.connect(self.filter)

    def filter(self, t):
        t = t.lower()
        for i in range(self.lst.count()):
            self.lst.item(i).setHidden(t not in self.lst.item(i).text().lower())

    def delete(self):
        for it in self.lst.selectedItems():
            self.on_delete(it.data(Qt.UserRole))
            self.lst.takeItem(self.lst.row(it))


class Main(QMainWindow):
    def __init__(self, profile, pprofile):
        super().__init__()
        self.profile, self.pprofile = profile, pprofile
        self.downloads = []
        self.setWindowTitle(APP)
        self.setWindowIcon(QIcon(os.path.join(RES, "supergo.png")))
        self.resize(1280, 800)
        root = QWidget()
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        side = QWidget()
        side.setFixedWidth(210)
        sv = QVBoxLayout(side)
        t = QLabel("<b>SUPERGO</b>")
        sv.addWidget(t)
        r = QHBoxLayout()
        for txt, fn in (("+ Tab", lambda: self.new_tab(HOME)), ("+ Private", lambda: self.new_tab(HOME, True))):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            r.addWidget(b)
        sv.addLayout(r)
        self.list = QListWidget()
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.tab_menu)
        sv.addWidget(self.list, 1)
        for txt, fn in (("Bookmarks", self.show_bookmarks), ("History", self.show_history),
                        ("Downloads", self.show_downloads), ("VPN...", self.vpn_dialog),
                        ("Home page...", self.set_home)):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            sv.addWidget(b)
        self.vpn_lbl = QLabel()
        self.vpn_lbl.setWordWrap(True)
        sv.addWidget(self.vpn_lbl)
        h.addWidget(side)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)
        bar = QHBoxLayout()
        bar.setContentsMargins(6, 6, 6, 6)
        self.btn = {}
        for key, txt, fn in (("back", "<", lambda: self.cur().back()), ("fwd", ">", lambda: self.cur().forward()),
                             ("rel", "R", lambda: self.cur().reload())):
            b = QPushButton(txt)
            b.setFixedWidth(34)
            b.clicked.connect(fn)
            bar.addWidget(b)
        self.addr = QLineEdit()
        self.addr.returnPressed.connect(lambda: self.cur().setUrl(fix_url(self.addr.text())))
        bar.addWidget(self.addr, 1)
        self.star = QPushButton("\u2606")
        self.star.setFixedWidth(34)
        self.star.clicked.connect(self.toggle_bookmark)
        bar.addWidget(self.star)
        rv.addLayout(bar)
        self.stack = QStackedWidget()
        rv.addWidget(self.stack, 1)
        h.addWidget(right, 1)

        self.list.currentRowChanged.connect(self.row_changed)
        for key, fn in (("Ctrl+T", lambda: self.new_tab(HOME)), ("Ctrl+Shift+N", lambda: self.new_tab(HOME, True)),
                        ("Ctrl+W", self.close_tab), ("Ctrl+L", lambda: (self.addr.setFocus(), self.addr.selectAll())),
                        ("F5", lambda: self.cur().reload()), ("Ctrl+D", self.toggle_bookmark),
                        ("Ctrl+H", self.show_history), ("Ctrl+J", self.show_downloads),
                        ("Alt+Left", lambda: self.cur().back()), ("Alt+Right", lambda: self.cur().forward()),
                        ("Ctrl+Tab", lambda: self.list.setCurrentRow((self.list.currentRow() + 1) % self.list.count()))):
            QShortcut(QKeySequence(key), self, activated=fn)
        for p in (profile, pprofile):
            p.downloadRequested.connect(self.on_download)

        urls = [u for u in jload("session.json", []) if isinstance(u, str)]
        for u in urls or [HOME]:
            self.new_tab(u, focus=False)
        self.list.setCurrentRow(0)
        self.tm = QTimer(self)
        self.tm.timeout.connect(self.tick)
        self.tm.start(2000)
        self.tick()
        if vpn_error:
            QTimer.singleShot(500, lambda: QMessageBox.warning(self, APP, "VPN could not start:\n" + vpn_error +
                              "\n\nWeb traffic is blocked until you fix or disable the VPN."))

    # ---- tabs ----
    def cur(self):
        return self.stack.currentWidget()

    def new_tab(self, url=None, private=False, focus=True):
        v = View(self, self.pprofile if private else self.profile, private)
        self.stack.addWidget(v)
        it = QListWidgetItem(("[P] " if private else "") + "New tab")
        self.list.addItem(it)
        v.titleChanged.connect(lambda t, v=v: self.set_title(v, t))
        v.iconChanged.connect(lambda ic, v=v: self.set_icon(v, ic))
        v.urlChanged.connect(lambda u, v=v: self.url_changed(v, u))
        v.loadFinished.connect(lambda ok, v=v: self.loaded(v, ok))
        if url:
            v.setUrl(fix_url(url))
        if focus:
            self.list.setCurrentRow(self.list.count() - 1)
        return v

    def item_of(self, v):
        i = self.stack.indexOf(v)
        return self.list.item(i) if i >= 0 else None

    def set_title(self, v, t):
        it = self.item_of(v)
        if it:
            it.setText(("[P] " if v.private else "") + (t or "New tab")[:40])
        if v is self.cur():
            self.setWindowTitle((t or "") + " - " + APP)

    def set_icon(self, v, ic):
        it = self.item_of(v)
        if it:
            it.setIcon(ic)

    def row_changed(self, row):
        if row >= 0:
            self.stack.setCurrentIndex(row)
            v = self.cur()
            self.addr.setText(v.url().toString())
            self.setWindowTitle((v.title() or "") + " - " + APP)
            self.update_star()

    def url_changed(self, v, u):
        if v is self.cur():
            if not self.addr.hasFocus():
                self.addr.setText(u.toString())
            self.update_star()

    def loaded(self, v, ok):
        u = v.url().toString()
        if ok and not v.private and u.startswith(("http://", "https://")):
            db.execute("INSERT INTO history(url,title,ts) VALUES(?,?,?) ON CONFLICT(url) DO UPDATE SET "
                       "title=excluded.title,ts=excluded.ts,visits=visits+1", (u, v.title(), time.time()))
            db.commit()

    def close_tab(self, row=None):
        row = self.list.currentRow() if row is None else row
        if row < 0:
            return
        v = self.stack.widget(row)
        self.stack.removeWidget(v)
        self.list.takeItem(row)
        v.deleteLater()
        if self.list.count() == 0:
            self.new_tab(HOME)
        else:
            self.stack.setCurrentIndex(max(0, self.list.currentRow()))

    def tab_menu(self, pos):
        it = self.list.itemAt(pos)
        if not it:
            return
        row = self.list.row(it)
        m = QMenu(self)
        m.addAction("Reload", lambda: self.stack.widget(row).reload())
        m.addAction("Duplicate", lambda: self.new_tab(self.stack.widget(row).url().toString(),
                                                      self.stack.widget(row).private))
        m.addAction("Close tab", lambda: self.close_tab(row))
        m.exec_(self.list.mapToGlobal(pos))

    # ---- bookmarks / history / downloads ----
    def update_star(self):
        u = self.cur().url().toString()
        self.star.setText("\u2605" if db.execute("SELECT 1 FROM bookmarks WHERE url=?", (u,)).fetchone() else "\u2606")

    def toggle_bookmark(self):
        v = self.cur()
        u = v.url().toString()
        if not u:
            return
        if db.execute("SELECT 1 FROM bookmarks WHERE url=?", (u,)).fetchone():
            db.execute("DELETE FROM bookmarks WHERE url=?", (u,))
        else:
            db.execute("INSERT OR REPLACE INTO bookmarks(url,title,ts) VALUES(?,?,?)", (u, v.title(), time.time()))
        db.commit()
        self.update_star()

    def _open(self, url):
        self.new_tab(url)

    def show_bookmarks(self):
        rows = [("%s\n%s" % (t or u, u), u) for u, t in db.execute("SELECT url,title FROM bookmarks ORDER BY ts DESC")]
        ListDialog(self, "Bookmarks", rows, self._open,
                   lambda u: (db.execute("DELETE FROM bookmarks WHERE url=?", (u,)), db.commit())).exec_()
        self.update_star()

    def show_history(self):
        rows = [("%s\n%s" % (t or u, u), u) for u, t in
                db.execute("SELECT url,title FROM history ORDER BY ts DESC LIMIT 500")]
        ListDialog(self, "History", rows, self._open,
                   lambda u: (db.execute("DELETE FROM history WHERE url=?", (u,)), db.commit()),
                   lambda: (db.execute("DELETE FROM history"), db.commit())).exec_()

    def on_download(self, d):
        os.makedirs(DLDIR, exist_ok=True)
        name = os.path.basename(d.path()) or "download"
        path, _ = QFileDialog.getSaveFileName(self, "Save file", os.path.join(DLDIR, name))
        if not path:
            d.cancel()
            return
        d.setPath(path)
        d.accept()
        self.downloads.append(d)
        self.statusBar().showMessage("Downloading " + os.path.basename(path), 4000)

    def show_downloads(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Downloads")
        dlg.resize(620, 400)
        lay = QVBoxLayout(dlg)
        lst = QListWidget()
        lay.addWidget(lst)
        lay.addWidget(QLabel("Double-click a finished item to open its folder."))

        def refresh():
            sel = lst.currentRow()
            lst.clear()
            for d in reversed(self.downloads):
                st = d.state()
                tot = d.totalBytes()
                txt = ("done" if st == 2 else "failed" if st in (3, 4) else
                       ("%d%%" % (100 * d.receivedBytes() // tot) if tot > 0 else "..."))
                it = QListWidgetItem("%s  -  %s" % (os.path.basename(d.path()), txt))
                it.setData(Qt.UserRole, d.path())
                lst.addItem(it)
            lst.setCurrentRow(sel)

        lst.itemDoubleClicked.connect(lambda it: QDesktopServices.openUrl(
            QUrl.fromLocalFile(os.path.dirname(it.data(Qt.UserRole)))))
        t = QTimer(dlg)
        t.timeout.connect(refresh)
        t.start(700)
        refresh()
        dlg.exec_()

    def set_home(self):
        global HOME
        t, ok = QInputDialog.getText(self, "Home page", "URL:", text=HOME)
        if ok and t.strip():
            HOME = t.strip()
            CFG["home"] = HOME
            jsave("settings.json", CFG)

    # ---- VPN ----
    def tick(self):
        if not VPN_ON:
            self.vpn_lbl.setText("VPN: off")
            self.vpn_lbl.setStyleSheet("color:#8a8f9c")
        elif xray is not None and xray.poll() is None:
            self.vpn_lbl.setText("VPN: on (SOCKS %d)" % PORT)
            self.vpn_lbl.setStyleSheet("color:#5fd38d")
        else:
            self.vpn_lbl.setText("VPN: DOWN - web traffic paused")
            self.vpn_lbl.setStyleSheet("color:#ff6b6b")

    def vpn_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("VPN (only SUPERGO goes through it)")
        dlg.resize(560, 360)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Paste a vless / vmess / trojan / ss link, a subscription URL, or a v2ray JSON config.\n"
                             "Needs xray.exe (or v2ray.exe) next to SUPERGO.exe. SUPERGO restarts to apply."))
        ed = QPlainTextEdit(VPN.get("text", ""))
        lay.addWidget(ed)
        row = QHBoxLayout()
        on, off, cancel = QPushButton("Save && enable"), QPushButton("Disable VPN"), QPushButton("Cancel")
        for b in (on, off, cancel):
            row.addWidget(b)
        lay.addLayout(row)
        cancel.clicked.connect(dlg.reject)

        def enable():
            try:
                vpn.build_config(ed.toPlainText(), PORT)
            except Exception as e:
                QMessageBox.warning(dlg, APP, "Could not read that config:\n%s" % e)
                return
            if not vpn.find_core([BASE, DATA]):
                QMessageBox.information(dlg, APP, "Saved, but xray.exe / v2ray.exe was not found next to "
                                        "SUPERGO.exe yet. Put it there and restart.")
            jsave("vpn.json", {"enabled": True, "text": ed.toPlainText().strip(), "port": PORT})
            dlg.accept()
            self.restart()

        def disable():
            jsave("vpn.json", {"enabled": False, "text": ed.toPlainText().strip(), "port": PORT})
            dlg.accept()
            self.restart()

        on.clicked.connect(enable)
        off.clicked.connect(disable)
        dlg.exec_()

    def restart(self):
        global RESTART
        RESTART = True
        self.close()

    def closeEvent(self, e):
        jsave("session.json", [self.stack.widget(i).url().toString() for i in range(self.stack.count())
                               if not self.stack.widget(i).private and self.stack.widget(i).url().isValid()])
        e.accept()
        QApplication.quit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setWindowIcon(QIcon(os.path.join(RES, "supergo.png")))
    app.setStyleSheet(STYLE)
    app.aboutToQuit.connect(lambda: vpn.stop(xray))
    profile = QWebEngineProfile("supergo", app)
    profile.setPersistentStoragePath(P("profile"))
    profile.setCachePath(P("cache"))
    profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
    pprofile = QWebEngineProfile(app)  # no name = off-the-record (private tabs)
    win = Main(profile, pprofile)
    win.show()
    code = app.exec_()
    vpn.stop(xray)
    if RESTART:
        subprocess.Popen([sys.executable] if FROZEN else [sys.executable, os.path.abspath(__file__)], cwd=BASE)
    sys.exit(code)


if __name__ == "__main__":
    main()
