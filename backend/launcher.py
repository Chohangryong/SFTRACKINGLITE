from __future__ import annotations

import ctypes
import os
import socket
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

import httpx
import uvicorn

from app.core.config import APP_DATA_DIR_NAME, Settings
from app.main import create_app

HOST = "127.0.0.1"
PORT = 8000
APP_URL = f"http://{HOST}:{PORT}/lite"
HEALTH_URL = f"http://{HOST}:{PORT}/api/health"
STARTUP_TIMEOUT_SECONDS = 30


def _log_path() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    base_dir = Path(local_appdata) / APP_DATA_DIR_NAME if local_appdata else Path.home() / "AppData" / "Local" / APP_DATA_DIR_NAME
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "launcher.log"


def log_message(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with _log_path().open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def is_health_ready() -> bool:
    try:
        response = httpx.get(HEALTH_URL, timeout=1.0)
        return response.status_code == 200
    except Exception:
        return False


def is_port_in_use() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((HOST, PORT)) == 0


def show_error(message: str) -> None:
    log_message(f"error: {message}")
    try:
        ctypes.windll.user32.MessageBoxW(None, message, "SF Express Tracking Lite", 0x10)
    except Exception:
        print(message)


def wait_and_open_browser() -> None:
    deadline = time.time() + STARTUP_TIMEOUT_SECONDS
    log_message("browser wait thread started")
    while time.time() < deadline:
        if is_health_ready():
            log_message("health ready, opening browser")
            webbrowser.open(APP_URL)
            return
        time.sleep(0.5)
    show_error("서버가 시작되지 않았습니다. 잠시 후 다시 실행해 주세요.")


def main() -> None:
    try:
        log_message("launcher started")
        if is_health_ready():
            log_message("existing app detected, opening browser only")
            webbrowser.open(APP_URL)
            return

        if is_port_in_use():
            show_error("127.0.0.1:8000 포트를 다른 프로그램이 사용 중입니다. 해당 프로그램을 종료한 뒤 다시 실행해 주세요.")
            return

        settings = Settings(
            environment="production",
            enable_scheduler=False,
            frontend_origin=f"http://{HOST}:{PORT}",
        )
        log_message(
            f"starting uvicorn host={HOST} port={PORT} data_dir={settings.data_dir} frontend_dist={settings.frontend_dist_dir}"
        )

        threading.Thread(target=wait_and_open_browser, daemon=True).start()
        uvicorn.run(
            create_app(settings),
            host=HOST,
            port=PORT,
            log_level="warning",
            access_log=False,
            log_config=None,
        )
        log_message("uvicorn.run returned")
    except Exception as exc:
        log_message(f"unhandled exception: {exc}")
        log_message(traceback.format_exc())
        show_error("앱 실행 중 오류가 발생했습니다. launcher.log를 확인해 주세요.")


if __name__ == "__main__":
    main()
