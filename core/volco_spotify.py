import subprocess
import os
from core.platform_support import command_exists, librespot_backend_args, spotify_cache_path

class VolcoSpotifyManager:
    def __init__(self):
        self.process = None
        self.cache_path = spotify_cache_path()
        self.initial_volume = 100

    def _get_user_id(self):
        env_user_id = os.environ.get("VOLCO_USER_ID", "").strip()
        if env_user_id:
            return env_user_id

        memory_path = os.path.join(os.path.dirname(__file__), "current_user.txt")
        try:
            with open(memory_path, "r") as f:
                return f.read().strip() or "OFFLINE_MODE"
        except OSError:
            return "OFFLINE_MODE"

    def _print_status(self, connected):
        state = "connected" if connected else "not connected"
        print(f"🎵 [SPOTIFY] user_id={self._get_user_id()} | volume={self.initial_volume}% | {state}")

    def start_client(self):
        """Launches librespot when it is installed on this machine."""
        if self.process and self.process.poll() is None:
            self._print_status(True)
            return

        if not command_exists("librespot"):
            print("🎵 [SPOTIFY] librespot not found; standalone Spotify client disabled.")
            self._print_status(False)
            return

        cmd = [
            "librespot",
            "--name", "Volco",
            "--cache", self.cache_path,
            "--bitrate", "320",
            "--initial-volume", str(self.initial_volume),
            "--device-type", "speaker",
            "--enable-volume-normalisation"
        ]
        cmd.extend(librespot_backend_args())

        try:
            os.makedirs(self.cache_path, exist_ok=True)
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._print_status(True)
        except Exception as e:
            self.process = None
            print(f"🎵 [SPOTIFY] Could not start librespot: {e}")
            self._print_status(False)

    def stop_client(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None
        self._print_status(False)

    def is_running(self):
        return self.process and self.process.poll() is None
