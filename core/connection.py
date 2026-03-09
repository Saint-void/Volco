import time
import asyncio
import threading
import queue
import aiohttp
import traceback
from aiortc import RTCPeerConnection, RTCSessionDescription
from config.config_manager import config
from core.audio_io import play_sfx  

class ConnectionManager:
    def __init__(self):
        self.ws_url = config["server"]["ws_url"]
        base_url = self.ws_url.split("/volco_ws")[0].replace("ws://", "http://")
        self.signaling_url = f"{base_url}/volco_webrtc/offer"
        
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

    # ⚡ THE TRACER: Now requires a "reason" so we know exactly who killed it
    def set_offline(self, reason="Unknown Call"):
        if self.is_running:
            print(f"\n⚠️ [NETWORK] Brain connection lost! 🕵️ TRACE: {reason}")
            play_sfx("./assets/sounds/shutdown.wav", async_play=True)
            self.is_running = False
            self.connected_event.clear()

    def connect(self):
        print(f"🔌 Signaling Brain at {self.signaling_url}...")
        self.connected_event.clear()
        self.handshake_success = False
        
        if self.webrtc_thread is None or not self.webrtc_thread.is_alive():
            self.loop = asyncio.new_event_loop()
            self.webrtc_thread = threading.Thread(target=self._run_loop, args=(self.loop,), daemon=True)
            self.webrtc_thread.start()
            time.sleep(0.5) 
        
        # ⚡ PYLANCE FIX: Prove loop exists before using it
        if self.loop is None:
            return False

        future = asyncio.run_coroutine_threadsafe(self._async_connect(), self.loop)
        success = self.connected_event.wait(timeout=20.0)
        
        if success and self.handshake_success:
            print("✅ Brain Connected (UDP Firehose Active)!")
            play_sfx("./assets/sounds/bt_connected.wav", async_play=True)
            self.is_running = True
            return True
        else:
            print("⚠️ Brain Offline: Signaling Failed or Timed Out.")
            self.set_offline("Handshake Timed Out")
            return False

    async def _async_connect(self):
        """The actual WebRTC Handshake (SDP Offer -> Answer)."""
        try:
            print("   -> [DEBUG] Creating PeerConnection...")
            self.pc = RTCPeerConnection()
            
            # ⚡ THE RAW FIREHOSE FIX: ordered=False, maxRetransmits=0
            # This physically stops WebRTC from acting like TCP. 
            # If a packet drops, it ignores the error and keeps firing audio anyway!
            self.channel = self.pc.createDataChannel(
                "volco_audio", 
                ordered=False, 
                maxRetransmits=0
            )

            @self.channel.on("message")
            def on_message(message):
                self.receive_queue.put(message)

            @self.pc.on("connectionstatechange")
            async def on_connectionstatechange():
                # ⚡ PYLANCE FIX: Safety check for self.pc
                if self.pc is None:
                    return
                    
                if self.pc.connectionState in ["failed", "closed"]:
                    # TRACE: Did the WebRTC state crash?
                    self.set_offline(f"WebRTC Status changed to: {self.pc.connectionState}")

            offer = await self.pc.createOffer()
            await self.pc.setLocalDescription(offer)

            payload = {
                "sdp": self.pc.localDescription.sdp, 
                "type": self.pc.localDescription.type,
                "user_id": "sogolo"
            }
            
            # ⚡ PYLANCE FIX: Use the strict aiohttp timeout object
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=20.0)
                async with session.post(self.signaling_url, json=payload, timeout=timeout) as resp:
                    if resp.status != 200:
                        raise Exception(f"Bad Gateway or Server Error: {resp.status}")
                    
                    # ⚡ REPAIRED BLOCK: This was missing in your paste!
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

    def is_connected(self):
        return self.is_running and self.channel and self.channel.readyState == "open"

    def send_ping(self):
        if self.is_connected() and (time.time() - self.last_ping > 2):
            self.send_data("PING")
            self.last_ping = time.time()

    def send_data(self, data):
        if not self.is_connected(): return False
        
        # ⚡ PYLANCE FIX: Prove loop exists before sending
        if self.loop is None: return False
        
        asyncio.run_coroutine_threadsafe(self._async_send(data), self.loop)
        return True

    async def _async_send(self, data):
        if self.channel and self.channel.readyState == "open":
            try:
                self.channel.send(data)
            except Exception as e:
                # ⚡ TRACE: Did the UDP send command crash?
                self.set_offline(f"UDP Channel Send Error: {e}")

    def recv_data(self):
        """Pure, infinite loop. No timers. No dropping connections."""
        while self.is_running:
            try:
                # We use a tiny 0.1s check just so it doesn't hard-lock the CPU, 
                # but we removed ALL the connection dropping logic!
                data = self.receive_queue.get(timeout=0.1)
                
                if isinstance(data, bytes): 
                    return (2, data)
                else: 
                    return (1, data)
                    
            except queue.Empty:
                # The queue is empty? Who cares. Keep waiting forever.
                continue 
                
        # It will only reach here if the network physically dies.
        raise Exception("Connection closed")

    def close(self):
        # ⚡ TRACE: Did another script explicitly tell us to hang up?
        self.set_offline("conn_manager.close() was explicitly called by another script!")
        if self.pc and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.pc.close(), self.loop)