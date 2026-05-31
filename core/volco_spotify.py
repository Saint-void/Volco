import subprocess
import os

class VolcoSpotifyManager:
    def __init__(self):
        self.process = None
        # Point straight to the folder where we trapped the VIP pass
        self.cache_path = "/home/volco/.cache/volco_spotify"
        self.initial_volume = 100

    def _get_user_id(self):
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
        """Launches librespot using the cached Google SSO Token!"""
        if self.process and self.process.poll() is None:
            self._print_status(True)
            return

        cmd = [
            "librespot",
            "--name", "Volco",
            "--cache", self.cache_path,
            "--backend", "alsa",
            "--bitrate", "320",
            "--initial-volume", str(self.initial_volume),
            "--device-type", "speaker",
            "--enable-volume-normalisation"
        ]

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._print_status(True)

    def stop_client(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
        self._print_status(False)

    def is_running(self):
        return self.process and self.process.poll() is None
