import subprocess
import os

class VolcoSpotifyManager:
    def __init__(self):
        self.process = None
        # Point straight to the folder where we trapped the VIP pass
        self.cache_path = "/home/volco/.cache/volco_spotify"

    def start_client(self):
        """Launches librespot using the cached Google SSO Token!"""
        if self.process and self.process.poll() is None:
            return

        print("🎸 [SPOTIFY] Booting Standalone Engine with Cached Token...")
        
        cmd = [
            "librespot",
            "--name", "Volco",
            "--cache", self.cache_path,
            "--backend", "alsa",
            "--bitrate", "320",
            "--initial-volume", "75",
            "--device-type", "speaker",
            "--enable-volume-normalisation",
            "--zeroconf-port", "0"
        ]

        # Launch the standalone client
        self.process = subprocess.Popen(cmd)
        print("✅ [SPOTIFY] Volco is Online and Logged In!")

    def stop_client(self):
        if self.process:
            print("🛑 [SPOTIFY] Shutting down Spotify Engine...")
            self.process.terminate()
            self.process.wait()
            self.process = None

    def is_running(self):
        return self.process and self.process.poll() is None