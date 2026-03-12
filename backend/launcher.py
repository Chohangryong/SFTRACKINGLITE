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
RECONNECT_TIMEOUT_SECONDS = 8


def _log_path() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    base_dir = (
        Path(local_appdata) / APP_DATA_DIR_NAME
        if local_appdata
        else Path.home() / "AppData" / "Local" / APP_DATA_DIR_NAME
    )
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "launcher.log"


def log_message(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with _log_path().open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def get_health_state() -> dict[str, object] | None:
    try:
        response = httpx.get(HEALTH_URL, timeout=1.0)
        if response.status_code != 200:
            return None
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


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
        if get_health_state():
            log_message("health ready, opening browser")
            webbrowser.open(APP_URL)
            return
        time.sleep(0.5)
    show_error("서버가 시작되지 않았습니다. 잠시 후 다시 실행해 주세요.")


def try_attach_to_existing_server() -> bool:
    health = get_health_state()
    if not health:
        return False

    if not bool(health.get("shutting_down", False)):
        log_message("existing app detected, opening browser only")
        webbrowser.open(APP_URL)
        return True

    log_message("existing app detected in shutting_down state, opening browser and waiting for reconnect")
    webbrowser.open(APP_URL)

    deadline = time.time() + RECONNECT_TIMEOUT_SECONDS
    while time.time() < deadline:
        health = get_health_state()
        if not health:
            if not is_port_in_use():
                log_message("existing shutting_down app exited before reconnect; starting new server")
                return False
            time.sleep(0.5)
            continue
        if not bool(health.get("shutting_down", False)):
            log_message("existing app canceled shutdown after reconnect; reusing server")
            return True
        time.sleep(0.5)

    log_message("existing app still shutting_down after reconnect window; reusing current server")
    return True


def main() -> None:
    try:
        log_message("launcher started")
        if try_attach_to_existing_server():
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

        server: uvicorn.Server | None = None

        def request_shutdown(reason: str) -> None:
            nonlocal server
            log_message(f"shutdown requested: {reason}")
            if server is not None:
                server.should_exit = True

        app = create_app(
            settings,
            shutdown_requester=request_shutdown,
            runtime_logger=log_message,
        )
        config = uvicorn.Config(
            app,
            host=HOST,
            port=PORT,
            log_level="warning",
            access_log=False,
            log_config=None,
        )
        server = uvicorn.Server(config)

        threading.Thread(target=wait_and_open_browser, daemon=True).start()
        server.run()
        log_message("uvicorn server exited")
    except Exception as exc:
        log_message(f"unhandled exception: {exc}")
        log_message(traceback.format_exc())
        show_error("앱 실행 중 오류가 발생했습니다. launcher.log를 확인해 주세요.")


if __name__ == "__main__":
    main()
