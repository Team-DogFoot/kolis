@echo off
rem Dev launcher: opens the program window (WebView2) with remote debugging port 9333 so Playwright can click real buttons. Normal use: app.vbs.
rem Do NOT parse .env here (batch for/f mangled UTF-8 BOM and Korean comments and set a wrong account once, 2026-10-03). Python reads .env itself.
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
set WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9333
start "" ".venv\Scripts\pythonw.exe" -m kolis_tool.app
