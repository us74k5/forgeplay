from __future__ import annotations

import ctypes
from ctypes import wintypes
from contextlib import asynccontextmanager, suppress
from html import escape
import json
import logging
from logging.handlers import RotatingFileHandler
import mimetypes
import os
from pathlib import Path
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from fastapi import Body, FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import yt_dlp


APP_NAME = "ForgePlay"
APP_VERSION = "1.0.0"
HOST = "127.0.0.1"
PORT = 8000
BASE_URL = f"http://{HOST}:{PORT}"
CACHE_MAX_AGE_SECONDS = 24 * 60 * 60
SERVER_STARTUP_TIMEOUT_SECONDS = 30
MUTEX_NAME = r"Local\ForgePlayHelper"
SHUTDOWN_EVENT_NAME = r"Local\ForgePlayHelperShutdown"


def _local_appdata_dir() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / APP_NAME
    return Path.home() / "AppData" / "Local" / APP_NAME


APP_DIR = _local_appdata_dir()
LOG_PATH = APP_DIR / "forgeplay.log"
CACHE_DIR = APP_DIR / "cache"


def configure_logging() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)

    handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root_logger.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "yt_dlp"):
        package_logger = logging.getLogger(logger_name)
        package_logger.handlers.clear()
        package_logger.propagate = True

    logging.captureWarnings(True)


configure_logging()
log = logging.getLogger("forgeplay")


def log_event(level: int, event: str, **fields: object) -> None:
    log.log(
        level,
        "event=%s details=%s",
        event,
        json.dumps(fields, default=str, sort_keys=True),
    )


def install_exception_hooks() -> None:
    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        log.critical(
            "Uncaught process exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        if sys.stderr:
            with suppress(Exception):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)

    def handle_thread_exception(args: threading.ExceptHookArgs) -> None:
        thread_name = args.thread.name if args.thread else "unknown"
        log.critical(
            "Uncaught thread exception in %s",
            thread_name,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        if sys.stderr and hasattr(threading, "__excepthook__"):
            with suppress(Exception):
                threading.__excepthook__(args)

    sys.excepthook = handle_exception
    if hasattr(threading, "excepthook"):
        threading.excepthook = handle_thread_exception


install_exception_hooks()


shutdown_event = threading.Event()
download_states: dict[str, dict[str, object]] = {}
download_states_lock = threading.Lock()
cleanup_thread_started = False
cleanup_thread_lock = threading.Lock()
server_state: dict[str, object] = {"server": None}
mutex_handle: int | None = None
windows_shutdown_event_handle: int | None = None
kernel32 = None


VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
ALLOWED_VIDEO_HOSTS = {
    "youtu.be",
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}


class DownloadRequest(BaseModel):
    url: str
    quality: str = "720"


PLAYER_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ForgePlay Player</title>
<style>
html, body {
    margin: 0;
    width: 100%;
    height: 100%;
    background: #050505;
    overflow: hidden;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
video {
    width: 100vw;
    height: 100vh;
    display: block;
    background: #000;
}
#fallback {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    background: rgba(0, 0, 0, 0.42);
}
#fallback[hidden] {
    display: none;
}
#playButton {
    border: 0;
    border-radius: 6px;
    background: #fff;
    color: #111;
    font: 600 16px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    padding: 14px 20px;
    cursor: pointer;
}
</style>
</head>
<body>
<video
    id="player"
    controls
    autoplay
    playsinline
    preload="auto">
    <source src="/media/__VIDEO_ID__">
</video>

<div id="fallback" hidden>
    <button id="playButton" type="button">Play Video</button>
</div>

<script>
(() => {
    const video = document.getElementById("player");
    const fallback = document.getElementById("fallback");
    const playButton = document.getElementById("playButton");

    function showFallback() {
        fallback.hidden = false;
    }

    function hideFallback() {
        fallback.hidden = true;
    }

    async function startPlayback(reason) {
        try {
            video.muted = false;
            video.defaultMuted = false;
            video.volume = 1.0;

            await video.play();

            hideFallback();
            console.info("ForgePlay playback started", reason);
        } catch (error) {
            console.warn("ForgePlay autoplay blocked", reason, error);
            showFallback();
        }
    }

    playButton.addEventListener("click", () => {
        startPlayback("user-gesture");
    });

    window.addEventListener("load", () => {
        startPlayback("window-load");
    });

    video.addEventListener("canplay", () => {
        if (video.paused) {
            startPlayback("canplay");
        }
    }, { once: true });

})();
</script>
</body>
</html>
"""

def validate_video_id(video_id: str) -> bool:
    return bool(video_id and VIDEO_ID_RE.fullmatch(video_id))


def validate_video_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in ALLOWED_VIDEO_HOSTS:
        log_event(logging.WARNING, "download_rejected_url", host=host, scheme=parsed.scheme)
        raise HTTPException(status_code=400, detail="Only YouTube URLs are supported")


def normalize_quality(quality: str) -> str:
    value = str(quality or "720")
    if value not in {"480", "720", "1080"}:
        log_event(logging.WARNING, "download_invalid_quality", quality=value)
        return "720"
    return value


def format_for_quality(quality: str) -> str:
    height = normalize_quality(quality)
    return f"best[height<={height}][ext=mp4]/best[height<={height}]/best"


def update_download_state(video_id: str, **state: object) -> None:
    if not validate_video_id(video_id):
        return
    state["updatedAt"] = int(time.time())
    with download_states_lock:
        download_states[video_id] = state


def make_progress_hook(video_ref: dict[str, str]):
    last_progress_log = {"at": 0.0}

    def progress_hook(event: dict[str, object]) -> None:
        video_id = video_ref.get("id", "")
        status = str(event.get("status", "unknown"))

        if status == "downloading":
            downloaded = event.get("downloaded_bytes")
            total = event.get("total_bytes") or event.get("total_bytes_estimate")
            update_download_state(
                video_id,
                status="downloading",
                downloadedBytes=downloaded,
                totalBytes=total,
            )
            now = time.time()
            if now - last_progress_log["at"] >= 30:
                last_progress_log["at"] = now
                log_event(
                    logging.INFO,
                    "download_progress",
                    videoId=video_id,
                    downloadedBytes=downloaded,
                    totalBytes=total,
                )
            return

        if status == "finished":
            filename = event.get("filename")
            update_download_state(video_id, status="ready", filename=filename)
            log_event(logging.INFO, "download_finished", videoId=video_id, filename=filename)

    return progress_hook


def purge_old_cache() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    now = time.time()

    for path in CACHE_DIR.iterdir():
        if not path.is_file():
            continue
        try:
            if now - path.stat().st_mtime > CACHE_MAX_AGE_SECONDS:
                path.unlink()
                log_event(logging.INFO, "cache_file_deleted", path=path)
        except Exception:
            log.exception("Failed deleting cache file: %s", path)


def cleanup_loop() -> None:
    while not shutdown_event.is_set():
        purge_old_cache()
        shutdown_event.wait(60 * 60)


def start_cleanup_thread() -> None:
    global cleanup_thread_started
    with cleanup_thread_lock:
        if cleanup_thread_started:
            return
        cleanup_thread_started = True
        thread = threading.Thread(
            target=cleanup_loop,
            name="cache-cleanup",
            daemon=True,
        )
        thread.start()
        log_event(logging.INFO, "cache_cleanup_thread_started", cacheDir=CACHE_DIR)


def find_cached_file(video_id: str) -> Path | None:
    if not validate_video_id(video_id):
        return None

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ignored_suffixes = {".part", ".ytdl", ".tmp", ".temp"}

    for path in CACHE_DIR.iterdir():
        if not path.is_file():
            continue
        if path.name.startswith(f"{video_id}.") and path.suffix.lower() not in ignored_suffixes:
            return path

    return None


def download_video_sync(request: DownloadRequest) -> dict[str, str]:
    validate_video_url(request.url)
    quality = normalize_quality(request.quality)

    log_event(logging.INFO, "download_requested", url=request.url, quality=quality)

    video_ref = {"id": ""}
    ydl_opts = {
        "format": format_for_quality(quality),
        "outtmpl": str(CACHE_DIR / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "cachedir": False,
        "quiet": True,
        "no_warnings": False,
        "logger": log,
        "progress_hooks": [make_progress_hook(video_ref)],
        "restrictfilenames": True,
        "windowsfilenames": True,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=False)
            video_id = str(info.get("id") or "")
            if not validate_video_id(video_id):
                log_event(logging.ERROR, "download_invalid_video_id", videoId=video_id)
                raise HTTPException(status_code=500, detail="Invalid video identifier")

            video_ref["id"] = video_id
            cached = find_cached_file(video_id)

            if cached:
                update_download_state(video_id, status="ready", filename=str(cached))
                log_event(logging.INFO, "download_cache_hit", videoId=video_id, path=cached)
            else:
                update_download_state(video_id, status="starting")
                log_event(logging.INFO, "download_starting", videoId=video_id, quality=quality)
                ydl.download([request.url])
                cached = find_cached_file(video_id)
                if not cached:
                    log_event(logging.ERROR, "download_missing_output", videoId=video_id)
                    raise HTTPException(status_code=500, detail="Downloaded file was not found")
                update_download_state(video_id, status="ready", filename=str(cached))

        return {"playerUrl": f"{BASE_URL}/player/{video_id}"}

    except HTTPException:
        raise
    except Exception:
        log.exception("Download failed")
        raise HTTPException(status_code=500, detail="Download failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    log_event(logging.INFO, "api_startup", host=HOST, port=PORT, cacheDir=CACHE_DIR)
    start_cleanup_thread()
    try:
        yield
    finally:
        log_event(logging.INFO, "api_shutdown")


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"status": "ok"}


@app.post("/download")
async def download_video(request: DownloadRequest = Body(...)):
    return await run_in_threadpool(download_video_sync, request)


@app.get("/player/{video_id}", response_class=HTMLResponse)
async def player(video_id: str):
    if not validate_video_id(video_id):
        log_event(logging.WARNING, "player_invalid_video_id", videoId=video_id)
        raise HTTPException(status_code=404, detail="Video not found")

    log_event(logging.INFO, "player_opened", videoId=video_id)
    return PLAYER_TEMPLATE.replace("__VIDEO_ID__", escape(video_id, quote=True))


@app.get("/media/{video_id}")
async def media(video_id: str):
    path = find_cached_file(video_id)

    if not path:
        log_event(logging.WARNING, "media_not_found", videoId=video_id)
        raise HTTPException(status_code=404, detail="Video not found")

    media_type, _ = mimetypes.guess_type(path.name)
    log_event(logging.INFO, "media_served", videoId=video_id, path=path)
    return FileResponse(str(path), media_type=media_type or "application/octet-stream")


@app.get("/progress/{video_id}")
async def progress(video_id: str):
    if find_cached_file(video_id):
        return {"status": "ready"}

    with download_states_lock:
        state = download_states.get(video_id)

    if state:
        return state

    return {"status": "unknown"}


def get_kernel32():
    global kernel32

    if os.name != "nt":
        return None

    if kernel32 is None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    return kernel32


def acquire_single_instance_mutex() -> bool:
    global kernel32, mutex_handle

    if os.name != "nt":
        return True

    winapi = get_kernel32()
    winapi.CreateMutexW.argtypes = [
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    winapi.CreateMutexW.restype = wintypes.HANDLE

    mutex_handle = winapi.CreateMutexW(None, False, MUTEX_NAME)
    if not mutex_handle:
        raise ctypes.WinError(ctypes.get_last_error())

    already_exists = ctypes.get_last_error() == 183
    if already_exists:
        log_event(logging.WARNING, "duplicate_instance_detected", mutex=MUTEX_NAME)
        return False

    log_event(logging.INFO, "single_instance_mutex_acquired", mutex=MUTEX_NAME)
    return True


def release_single_instance_mutex() -> None:
    global mutex_handle

    if os.name != "nt" or not mutex_handle or kernel32 is None:
        return

    with suppress(Exception):
        kernel32.CloseHandle(mutex_handle)
    mutex_handle = None


def create_windows_shutdown_event() -> None:
    global windows_shutdown_event_handle

    if os.name != "nt":
        return

    winapi = get_kernel32()
    winapi.CreateEventW.argtypes = [
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    winapi.CreateEventW.restype = wintypes.HANDLE

    windows_shutdown_event_handle = winapi.CreateEventW(
        None,
        False,
        False,
        SHUTDOWN_EVENT_NAME,
    )
    if not windows_shutdown_event_handle:
        raise ctypes.WinError(ctypes.get_last_error())

    log_event(logging.INFO, "shutdown_signal_event_created", eventName=SHUTDOWN_EVENT_NAME)


def release_windows_shutdown_event() -> None:
    global windows_shutdown_event_handle

    if os.name != "nt" or not windows_shutdown_event_handle or kernel32 is None:
        return

    with suppress(Exception):
        kernel32.CloseHandle(windows_shutdown_event_handle)
    windows_shutdown_event_handle = None


def signal_existing_instance_shutdown() -> bool:
    if os.name != "nt":
        return False

    event_modify_state = 0x0002
    winapi = get_kernel32()
    winapi.OpenEventW.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    winapi.OpenEventW.restype = wintypes.HANDLE
    winapi.SetEvent.argtypes = [wintypes.HANDLE]
    winapi.SetEvent.restype = wintypes.BOOL

    event_handle = winapi.OpenEventW(event_modify_state, False, SHUTDOWN_EVENT_NAME)
    if not event_handle:
        log_event(logging.WARNING, "shutdown_signal_event_missing", eventName=SHUTDOWN_EVENT_NAME)
        return False

    try:
        signaled = bool(winapi.SetEvent(event_handle))
        log_event(logging.INFO, "shutdown_signal_sent", signaled=signaled)
        return signaled
    finally:
        with suppress(Exception):
            winapi.CloseHandle(event_handle)


def wait_for_windows_shutdown_signal(icon) -> None:
    if os.name != "nt" or not windows_shutdown_event_handle or kernel32 is None:
        return

    infinite = 0xFFFFFFFF
    wait_object_0 = 0

    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD

    result = kernel32.WaitForSingleObject(windows_shutdown_event_handle, infinite)
    if result == wait_object_0:
        log_event(logging.INFO, "shutdown_signal_received")
        request_shutdown(icon)
    else:
        log_event(logging.WARNING, "shutdown_signal_wait_failed", result=result)


def is_port_available() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1)
        try:
            probe.bind((HOST, PORT))
            return True
        except OSError as exc:
            log_event(logging.WARNING, "server_port_unavailable", host=HOST, port=PORT, error=exc)
            return False


def helper_healthcheck(timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/", timeout=timeout) as response:
            body = response.read(200)
            return response.status == 200 and b'"status":"ok"' in body.replace(b" ", b"")
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def wait_for_server_ready(timeout: int = SERVER_STARTUP_TIMEOUT_SECONDS) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline and not shutdown_event.is_set():
        if helper_healthcheck(timeout=0.5):
            return True
        time.sleep(0.5)
    return False


def run_server() -> None:
    import uvicorn

    attempt = 0
    while not shutdown_event.is_set():
        attempt += 1

        if not is_port_available():
            if helper_healthcheck(timeout=1):
                log_event(logging.WARNING, "server_already_running_on_port", port=PORT)
                shutdown_event.set()
                return

            delay = min(30, 2 ** min(attempt, 5))
            log_event(
                logging.WARNING,
                "server_bind_retry_scheduled",
                attempt=attempt,
                delaySeconds=delay,
            )
            shutdown_event.wait(delay)
            continue

        try:
            log_event(logging.INFO, "server_starting", host=HOST, port=PORT, attempt=attempt)
            config = uvicorn.Config(
                app,
                host=HOST,
                port=PORT,
                log_level="info",
                log_config=None,
                access_log=False,
            )
            server = uvicorn.Server(config)
            server_state["server"] = server
            server.run()

            if shutdown_event.is_set() or server.should_exit:
                log_event(logging.INFO, "server_stopped")
                return

            log_event(logging.WARNING, "server_exited_unexpectedly")

        except BaseException as exc:
            log.exception("Server crashed: %s", exc)
        finally:
            server_state["server"] = None

        if not shutdown_event.is_set():
            delay = min(30, 2 ** min(attempt, 5))
            log_event(
                logging.WARNING,
                "server_crash_retry_scheduled",
                attempt=attempt,
                delaySeconds=delay,
            )
            shutdown_event.wait(delay)


def tray_image():
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 56, 56), fill=(35, 104, 230, 255))
    draw.polygon(((28, 21), (28, 43), (45, 32)), fill=(255, 255, 255, 255))
    return image


def open_control(*_) -> None:
    import webbrowser

    log_event(logging.INFO, "tray_open_control")
    webbrowser.open(f"{BASE_URL}/docs")


def open_log_file(*_) -> None:
    log_event(logging.INFO, "tray_open_log", logPath=LOG_PATH)
    if os.name == "nt":
        os.startfile(str(LOG_PATH))  # type: ignore[attr-defined]


def request_shutdown(icon=None, *_):
    if not shutdown_event.is_set():
        log_event(logging.INFO, "shutdown_requested", source="tray")
    shutdown_event.set()

    server = server_state.get("server")
    if server is not None:
        with suppress(Exception):
            server.should_exit = True

    if icon is not None:
        with suppress(Exception):
            icon.stop()


def main() -> int:
    if any(arg.lower() in {"--shutdown", "--quit", "/shutdown", "/quit"} for arg in sys.argv[1:]):
        signaled = signal_existing_instance_shutdown()
        return 0 if signaled else 1

    log_event(
        logging.INFO,
        "process_start",
        version=APP_VERSION,
        pid=os.getpid(),
        executable=sys.executable,
        frozen=bool(getattr(sys, "frozen", False)),
        cwd=os.getcwd(),
        appDir=APP_DIR,
        cacheDir=CACHE_DIR,
        logPath=LOG_PATH,
        argv=sys.argv,
    )

    if not acquire_single_instance_mutex():
        if not helper_healthcheck(timeout=1):
            log_event(logging.ERROR, "duplicate_instance_unhealthy", action="exit")
        return 0

    create_windows_shutdown_event()

    try:
        import pystray
        from pystray import MenuItem as item
    except Exception:
        log.exception("Tray dependencies failed to load")
        release_single_instance_mutex()
        return 1

    purge_old_cache()

    server_thread = threading.Thread(
        target=run_server,
        name="uvicorn-server",
        daemon=True,
    )
    server_thread.start()

    if wait_for_server_ready():
        log_event(logging.INFO, "server_ready", url=BASE_URL)
    elif shutdown_event.is_set():
        log_event(logging.WARNING, "startup_aborted_before_tray")
        release_single_instance_mutex()
        return 0
    else:
        log_event(logging.ERROR, "server_not_ready_after_timeout", url=BASE_URL)

    tray = pystray.Icon(
        "ForgePlayHelper",
        tray_image(),
        "ForgePlay Helper",
        menu=pystray.Menu(
            item("Open Control", open_control),
            item("Open Log", open_log_file),
            item("Quit", request_shutdown),
        ),
    )

    threading.Thread(
        target=wait_for_windows_shutdown_signal,
        args=(tray,),
        name="shutdown-signal",
        daemon=True,
    ).start()

    try:
        tray.run()
    except Exception:
        log.exception("Tray crashed")
        request_shutdown()
        return 1
    finally:
        request_shutdown()
        server_thread.join(timeout=10)
        release_windows_shutdown_event()
        release_single_instance_mutex()
        log_event(logging.INFO, "process_exit")

    return 0


if __name__ == "__main__":
    sys.exit(main())
