import socket
import time
import websocket
from config.config_manager import config
from core.audio_io import play_sfx  

class ConnectionManager:
    def __init__(self):
        self.ws_url = config["server"]["ws_url"]
        self.ws = None
        self.last_ping = time.time()

    def set_offline(self):
        """Safely marks the connection as dead and plays the offline sound."""
        if self.ws is not None:
            print("\n⚠️ [NETWORK] Brain connection lost!")
            # ⚡ Update this to a voice line like "Server disconnected"
            play_sfx("./assets/sounds/shutdown.wav", async_play=True)

    def connect(self):
        """Attempts to connect to the Vella Server."""
        print(f"🔌 Connecting to Brain at {self.ws_url}...")
        try:
            self.ws = websocket.create_connection(self.ws_url, ping_interval=15, ping_timeout=10)
            print("✅ Brain Connected!")
            # ⚡ Update this to your new "Systems online" or "Server connected" voice file
            play_sfx("./assets/sounds/bt_connected.wav", async_play=True)
            return True
        except Exception as e:
            print(f"⚠️ Brain Offline: {e}")
            self.set_offline()
            return False

    def is_connected(self):
        """Checks if the socket is alive."""
        return self.ws is not None and self.ws.connected

    def send_ping(self):
        """Sends a heartbeat to keep the connection alive."""
        if self.ws and self.ws.connected and (time.time() - self.last_ping > 2):
            try:
                self.ws.send("PING")
                self.last_ping = time.time()
            except Exception:
                self.set_offline()

    def send_data(self, data):
        """Safely sends text or binary data."""
        if not self.ws or not self.ws.connected: 
            return False
            
        try:
            if isinstance(data, bytes):
                self.ws.send_binary(data)
            else:
                self.ws.send(data)
            return True
        except Exception:
            self.set_offline() 
            return False

    def recv_data(self):
        """Receives data from the socket."""
        if not self.ws or not self.ws.connected:
            raise Exception("Not connected")
            
        return self.ws.recv_data()

    def close(self):
        self.set_offline()