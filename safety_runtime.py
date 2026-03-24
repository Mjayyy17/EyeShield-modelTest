import os
import shutil
import traceback
from datetime import datetime
from pathlib import Path

APP_NAME = "DrScreening"


def get_app_support_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_NAME
    return Path.home() / "Library" / "Application Support" / APP_NAME


def get_logs_dir() -> Path:
    path = get_app_support_dir() / "Logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_results_dir() -> Path:
    path = get_app_support_dir() / "Results"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_autosave_draft_path() -> Path:
    return get_app_support_dir() / "autosave_draft.tmp"


def timestamp_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_activity(level: str, action: str, details: str) -> None:
    level_clean = (level or "INFO").upper().strip()
    action_clean = (action or "ACTION").strip()
    details_clean = (details or "").strip()
    line = f"[{timestamp_now()}] [{level_clean}] [{action_clean}] {details_clean}\n"

    log_file = get_logs_dir() / f"activity_{datetime.now().strftime('%Y-%m-%d')}.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line)


def write_crash_log(exc_type, exc_value, exc_tb, app_state: str = "") -> Path:
    crash_file = get_logs_dir() / f"crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    stack = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    with open(crash_file, "w", encoding="utf-8") as f:
        f.write(f"Timestamp: {timestamp_now()}\n")
        f.write(f"App state: {app_state}\n\n")
        f.write(stack)
    return crash_file


def get_free_space_mb(path_str: str) -> int:
    target = Path(path_str) if path_str else get_app_support_dir()
    target.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(target)
    return int(usage.free / (1024 * 1024))


def can_write_directory(path_str: str) -> tuple[bool, str]:
    try:
        target = Path(path_str)
        target.mkdir(parents=True, exist_ok=True)
        test_file = target / ".write_test.tmp"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("ok")
        test_file.unlink(missing_ok=True)
        return True, ""
    except OSError as err:
        return False, str(err)


def safe_remove_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
