import os
import platform
import shutil
import subprocess
from pathlib import Path


_SYSTEM = platform.system()
_OVERRIDE = os.environ.get("VOLCO_PLATFORM", "").strip().lower()


def system_name():
    if _OVERRIDE:
        return _OVERRIDE
    return _SYSTEM or "Unknown"


def is_macos():
    return _OVERRIDE in {"mac", "macos", "darwin"} or _SYSTEM == "Darwin"


def is_windows():
    return _OVERRIDE in {"win", "windows"} or _SYSTEM == "Windows"


def is_linux():
    return _OVERRIDE in {"linux", "pi", "raspberrypi", "raspberry-pi"} or _SYSTEM == "Linux"


def is_raspberry_pi():
    if _OVERRIDE in {"pi", "raspberrypi", "raspberry-pi"}:
        return True
    if not is_linux():
        return False

    for model_path in (
        "/proc/device-tree/model",
        "/sys/firmware/devicetree/base/model",
    ):
        try:
            model = Path(model_path).read_text(errors="ignore").lower()
            if "raspberry pi" in model:
                return True
        except OSError:
            continue
    return False


def platform_label():
    if is_raspberry_pi():
        return "Raspberry Pi"
    if is_macos():
        return "macOS"
    if is_windows():
        return "Windows"
    if is_linux():
        return "Linux"
    return system_name()


def command_exists(command):
    return shutil.which(command) is not None


def run_quiet(cmd, capture_output=False, text=True, timeout=None):
    try:
        if capture_output:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=text,
                timeout=timeout,
                check=False,
            )

        return subprocess.run(
            cmd,
            text=text,
            timeout=timeout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def popen_quiet(cmd):
    try:
        return subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return None


def can_use_bluez():
    return is_linux() and command_exists("bluetoothctl")


def can_use_bluealsa_bridge():
    return is_linux() and command_exists("bluealsa-aplay")


def can_use_rfcomm():
    return is_linux() and command_exists("rfcomm")


def can_use_gpio_button():
    return is_raspberry_pi() or os.environ.get("VOLCO_ENABLE_GPIO") == "1"


def spotify_cache_path():
    configured = os.environ.get("VOLCO_SPOTIFY_CACHE")
    if configured:
        return os.path.expanduser(configured)

    legacy_pi_path = Path("/home/volco/.cache/volco_spotify")
    if is_linux() and legacy_pi_path.exists():
        return str(legacy_pi_path)

    return str(Path.home() / ".cache" / "volco_spotify")


def librespot_backend_args():
    if is_linux():
        return ["--backend", "alsa"]
    return []
