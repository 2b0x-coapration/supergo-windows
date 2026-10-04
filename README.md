# SUPERGO 2.0 (Windows 7+ edition)

Flat dark browser with tabs in the sidebar. Uses **Qt5 QtWebEngine (Chromium 83)** - no WebView2, no .NET.

## Files (all in the repo root, no folders needed except one)
`supergo.py`, `vpn.py`, `supergo.ico`, `supergo.png`, `requirements.txt`, `build.bat`, `README.md`, and `build.yml` (8 files).

## Build on GitHub
1. Create a repo and upload the files above.
2. `build.yml` must live at `.github/workflows/build.yml`. On GitHub: **Add file -> Create new file**, type
   `.github/workflows/build.yml` as the name (typing `/` makes the folders) and paste the contents of `build.yml`.
3. Open the **Actions** tab -> run **Build SUPERGO (Windows 7+)** (it also runs on every push).
4. Download the `SUPERGO-win7` artifact (GitHub wraps it in a zip), unzip it and you get a single `SUPERGO.exe`.

Local build instead: install 64-bit Python 3.8 and double-click `build.bat`.

## Single-file note
The exe is one file (~100+ MB). It unpacks itself to a temp folder on each start, so launch takes a few seconds.

## Windows 7 notes
- Needs 64-bit Windows 7 **SP1** plus the "Universal C Runtime" update (KB2999226).
- If the window is black, set the environment variable `SUPERGO_SOFTWARE=1`.
- Chromium 83 is old: a few modern sites (e.g. some Google login pages) may refuse it.

## VPN (optional, only SUPERGO's traffic)
Put `xray.exe` next to `SUPERGO.exe`. **Official recent Xray builds do not run on Windows 7** (Go dropped Win7),
so use a Win7-compatible build (e.g. a community Go 1.20 build, or v2ray-core 4.45.2 as `v2ray.exe`).
Then click **VPN...**, paste a vless/vmess/trojan/ss link, subscription URL or JSON. If the tunnel drops, the
browser's traffic is blocked instead of leaking. (v2ray 4.x has no REALITY support.)

Data (history, bookmarks, session, settings) lives in `%APPDATA%\SUPERGO`.
Shortcuts: Ctrl+T, Ctrl+Shift+N (private), Ctrl+W, Ctrl+L, F5, Ctrl+D, Ctrl+H, Ctrl+J, Ctrl+Tab.
