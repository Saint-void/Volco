import time
import asyncio
import threading
import queue
import aiohttp
import traceback
import os # ⚡ Needed to check if the memory file exists
from aiortc import RTCPeerConnection, RTCSessionDescription
from config.config_manager import config
from core.audio_io import play_sfx  

def get_current_user_id():
    """Reads Volco's memory drive to see who currently owns the headset."""
    memory_path = "core/current_user.txt"
    if os.path.exists(memory_path):
        with open(memory_path, "r") as f:
            user_id = f.read().strip()
            if user_id:
                return user_id
    # Fallback to the default if nobody has ever synced the headset
    return "OFFLINE_MODE"

class ConnectionManager:
    def __init__(self):
        # 1. Get the raw URL from settings.json
        raw_ws_url = config["server"]["ws_url"]
        
        # 2. Slice off the hardcoded "user_id=sogolo" from the end of the string
        base_ws = raw_ws_url.split("&user_id=")[0]
        
        # 3. Get the REAL User ID from our memory drive
        self.active_user_id = get_current_user_id()
        
        # 4. Construct the true URLs!
        self.ws_url = f"{base_ws}&user_id={self.active_user_id}"
        
        base_http = self.ws_url.split("/volco_ws")[0].replace("ws://", "http://").replace("wss://", "https://")
        self.signaling_url = f"{base_http}/volco_webrtc/offer"
        
        print(f"📡 [NETWORK] Booting with Active Profile ID: {self.active_user_id}")
        
        self.pc = None
        self.channel = None
        self.last_ping = time.time()
        
        self.loop = None
        self.webrtc_thread = None
        self.receive_queue = queue.Queue()
        self.connected_event = threading.Event()
        self.is_running = False
        self.handshake_success = False

    def _run_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def set_offline(self, reason="Unknown Call"):
        if self.is_running:
            print(f"\n⚠️ [NETWORK] Brain connection lost! 🕵️ TRACE: {reason}")
            play_sfx("./assets/sounds/shutdown.wav", async_play=True)
            self.is_running = False
            self.connected_event.clear()

    def connect(self):
        # ⚡ 1. Read the memory drive EVERY time we try to connect
        self.active_user_id = get_current_user_id()
        
        # ⚡ 2. If it's a blank headset, ABORT the connection and wait!
        if self.active_user_id in ["OFFLINE_MODE", ""]:
            print("🛑 [NETWORK] Setup Mode: No User Profile found. Waiting for Volco App sync...")
            self.is_running = False
            return False
            
        # ⚡ 3. Re-build the URL with the fresh ID
        raw_ws_url = config["server"]["ws_url"]
        base_ws = raw_ws_url.split("&user_id=")[0]
        self.ws_url = f"{base_ws}&user_id={self.active_user_id}"
        
        base_http = self.ws_url.split("/volco_ws")[0].replace("ws://", "http://").replace("wss://", "https://")
        self.signaling_url = f"{base_http}/volco_webrtc/offer"

        print(f"🔌 Signaling Brain at {self.signaling_url}...")
        self.connected_event.clear()
        self.handshake_success = False
        
        if self.webrtc_thread is None or not self.webrtc_thread.is_alive():
            self.loop = asyncio.new_event_loop()
            self.webrtc_thread = threading.Thread(target=self._run_loop, args=(self.loop,), daemon=True)
            self.webrtc_thread.start()
            time.sleep(0.5) 
        
        if self.loop is None:
            return False

        future = asyncio.run_coroutine_threadsafe(self._async_connect(), self.loop)
        success = self.connected_event.wait(timeout=20.0)
        
        if success and self.handshake_success:
            print(f"✅ Brain Connected! Locked to Profile: {self.active_user_id}")
            play_sfx("./assets/sounds/vella_online.wav")
            self.is_running = True
            return True
        else:
            print("⚠️ Brain Offline: Signaling Failed or Timed Out.")
            self.set_offline("Handshake Timed Out")
            return False

    async def _async_connect(self):
        try:
            print("   -> [DEBUG] Creating PeerConnection...")
            self.pc = RTCPeerConnection()
            
            self.channel = self.pc.createDataChannel(
                "volco_audio", 
                ordered=True
            )

            @self.channel.on("message")
            def on_message(message):
                self.receive_queue.put(message)

            @self.pc.on("connectionstatechange")
            async def on_connectionstatechange():
                if self.pc is None:
                    return
                    
                if self.pc.connectionState in ["failed", "closed"]:
                    self.set_offline(f"WebRTC Status changed to: {self.pc.connectionState}")

            offer = await self.pc.createOffer()
            await self.pc.setLocalDescription(offer)

            # ⚡ INJECT THE REAL ID INTO THE PAYLOAD
            payload = {
                "sdp": self.pc.localDescription.sdp, 
                "type": self.pc.localDescription.type,
                "user_id": self.active_user_id 
            }
            
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=20.0)
                async with session.post(self.signaling_url, json=payload, timeout=timeout) as resp:
                    if resp.status != 200:
                        raise Exception(f"Bad Gateway or Server Error: {resp.status}")
                    
                    answer_data = await resp.json()

            answer = RTCSessionDescription(sdp=answer_data["sdp"], type=answer_data["type"])
            await self.pc.setRemoteDescription(answer)

            for _ in range(50):
                if self.channel.readyState == "open":
                    self.handshake_success = True
                    self.connected_event.set()
                    return
                await asyncio.sleep(0.1)

            self.connected_event.set()

        except Exception as e:
            print(f"⚠️ WebRTC Connection Error: {e}")
            self.connected_event.set()

    # (The rest of your ConnectionManager code remains exactly the same below here...)
    def is_connected(self):
        return self.is_running and self.channel and self.channel.readyState == "open"

    def send_ping(self):
        if self.is_connected() and (time.time() - self.last_ping > 2):
            self.send_data("PING")
            self.last_ping = time.time()

    def send_data(self, data, wait=False, timeout=2.0):
        if not self.is_connected(): return False
        if self.loop is None: return False
        future = asyncio.run_coroutine_threadsafe(self._async_send(data), self.loop)
        if wait:
            try:
                future.result(timeout=timeout)
            except Exception as e:
                self.set_offline(f"UDP Channel Send Wait Error: {e}")
                return False
        return True

    async def _async_send(self, data):
        if self.channel and self.channel.readyState == "open":
            try:
                self.channel.send(data)
            except Exception as e:
                self.set_offline(f"UDP Channel Send Error: {e}")

    def recv_data(self):
        while self.is_running:
            try:
                data = self.receive_queue.get(timeout=0.1)
                if isinstance(data, bytes): 
                    return (2, data)
                else: 
                    return (1, data)
            except queue.Empty:
                continue 
        raise Exception("Connection closed")

    def close(self):
        self.set_offline("conn_manager.close() was explicitly called by another script!")
        if self.pc and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.pc.close(), self.loop)
