"""
run.py
------
One-command launcher for YojanaBench.

    python run.py

Starts the FastAPI backend (which also serves the dashboard) and opens the UI
in the default browser. No build step, no API keys, no internet required.

Because the dashboard's voice assistant greets the user automatically, the
launcher prefers Chrome/Edge started with ``--autoplay-policy=
no-user-gesture-required`` (in an isolated profile) so the greeting is *spoken*
without needing a click - important for the blind/low-vision users this widget
is built for. If neither Chromium browser is found it silently falls back to the
system default browser (where the greeting simply waits for one tap).
"""
import os
import subprocess
import tempfile
import threading
import webbrowser

import uvicorn

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

# Chromium-based browsers we can nudge into autoplay-friendly mode.
_CHROMIUM_BROWSERS = [
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def _open_browser():
    profile = os.path.join(tempfile.gettempdir(), "yojanabench-profile")
    for exe in _CHROMIUM_BROWSERS:
        if not os.path.exists(exe):
            continue
        try:
            subprocess.Popen([
                exe,
                "--autoplay-policy=no-user-gesture-required",
                f"--user-data-dir={profile}",
                "--no-first-run",
                "--no-default-browser-check",
                URL,
            ])
            return
        except OSError:
            continue
    webbrowser.open(URL)


if __name__ == "__main__":
    print("=" * 64)
    print("  YojanaBench - welfare-scheme document reasoning & audit")
    print(f"  Dashboard: {URL}")
    print(f"  API docs : {URL}/docs")
    print("  The voice assistant opens and speaks automatically after a")
    print("  few seconds. If you do not hear it, tap the screen once.")
    print("=" * 64)
    threading.Timer(1.5, _open_browser).start()
    uvicorn.run("backend.app:app", host=HOST, port=PORT, reload=False)
