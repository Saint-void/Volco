import time
import json
import os
import base64
from wsgiref import headers
import requests
import urllib.parse
from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
import urllib.parse
import requests

# ⚡ YOUR SPOTIFY APP CREDENTIALS
CLIENT_ID = "ab7f761ecf374d629e3674d014674dd1"
CLIENT_SECRET = "65742ae20dac40e7ba963f151412a2b8"


class VolcoDiscoveryListener(ServiceListener):
    def add_service(self, zc, type_, name): 
        print(f"🔍 Found local service: {name}")
        pass
    def remove_service(self, zc, type_, name): 
        pass
    def update_service(self, zc, type_, name): 
        pass

class VolcoSpotifyEngine:
    def __init__(self):
        self.creds_path = os.path.expanduser("~/volco_spotify_creds.json")
        self.base_url = "https://api.spotify.com/v1"

    def _get_access_token(self):
        """Silently trades the permanent refresh token for a 60-minute access token."""
        try:
            with open(self.creds_path, "r") as f:
                data = json.load(f)
                refresh_token = data.get("refresh_token")

            auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
            b64_auth_str = base64.b64encode(auth_str.encode()).decode()

            headers = {
                "Authorization": f"Basic {b64_auth_str}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            payload = {"grant_type": "refresh_token", "refresh_token": refresh_token}
            
            res = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=payload)
            if res.status_code == 200:
                return res.json().get("access_token")
        except Exception as e:
            print(f"❌ Failed to get Spotify token: {e}")
        return None

    def _get_headers(self):
        token = self._get_access_token()
        return {"Authorization": f"Bearer {token}"} if token else None

    def discovery_ping(self):
        """Forces the Pi to broadcast itself and look for Spotify services locally."""
        print("📡 Sending Discovery Ping to local network...")
        
        zc = Zeroconf()
        try:
            # ⚡ Now we pass the properly typed listener
            listener = VolcoDiscoveryListener()
            browser = ServiceBrowser(zc, "_spotify-connect._tcp.local.", listener=listener)
            
            # Keep the searchlight on for 3 seconds
            time.sleep(3) 
            print("📡 Discovery broadcast complete.")
            
            # Give the Spotify Cloud 2 seconds to sync the wake-up signal
            print("⏳ Waiting for Spotify Cloud to sync...")
            time.sleep(2)
            
        except Exception as e:
            print(f"⚠️ Discovery error: {e}")
        finally:
            zc.close()

        

    # --- THE COMMANDS ---

    def play_resume(self):
        """Resumes current playback specifically on Volco."""
        headers = self._get_headers()
        if not headers: return
        
        device_id = self.get_volco_device_id(headers)
        device_query = f"?device_id={device_id}" if device_id else ""
        
        res = requests.put(f"{self.base_url}/me/player/play{device_query}", headers=headers)
        if res.status_code in [200, 202, 204]:
            print("▶️ Playing/Resuming music")
        else:
            print(f"❌ Resume failed: {res.status_code}")

    def pause(self):
        """Pauses current playback specifically on Volco."""
        headers = self._get_headers()
        if not headers: return
        
        device_id = self.get_volco_device_id(headers)
        device_query = f"?device_id={device_id}" if device_id else ""
        
        res = requests.put(f"{self.base_url}/me/player/pause{device_query}", headers=headers)
        if res.status_code in [200, 202, 204]:
            print("⏸️ Paused music")
        else:
            print(f"❌ Pause failed: {res.status_code}")

    def set_volume(self, volume_percent):
        """Sets the volume (0-100) specifically on Volco."""
        headers = self._get_headers()
        if not headers: 
            return
        
        # Target the Volco device specifically so we don't accidentally 
        # change the volume on your phone or TV.
        device_id = self.get_volco_device_id(headers)
        
        # Spotify Volume API uses a query parameter: ?volume_percent=X
        url = f"{self.base_url}/me/player/volume?volume_percent={volume_percent}"
        if device_id:
            url += f"&device_id={device_id}"
        
        try:
            res = requests.put(url, headers=headers)
            if res.status_code in [200, 202, 204]:
                print(f"🔊 Volume set to {volume_percent}%")
            else:
                print(f"❌ Volume change failed: {res.status_code}")
        except Exception as e:
            print(f"⚠️ Volume error: {e}")
    
    def fade_volume(self, target_volume, start_volume=93, duration=0.6):
        """Fades volume smoothly in the background without hitting Spotify API rate limits."""
        import threading
        import time
        import requests

        def _fade():
            headers = self._get_headers()
            if not headers: 
                return
            device_id = self.get_volco_device_id(headers)
            
            # We step the volume in 3 quick chunks to create a smooth illusion
            steps = 3 
            step_delay = duration / steps
            step_size = (target_volume - start_volume) / steps
            
            for i in range(1, steps + 1):
                # Calculate the exact volume for this step
                current_vol = int(start_volume + (step_size * i))
                
                # Safety check to keep it between 0 and 100
                current_vol = max(0, min(100, current_vol)) 
                
                url = f"{self.base_url}/me/player/volume?volume_percent={current_vol}"
                if device_id:
                    url += f"&device_id={device_id}"
                
                try:
                    requests.put(url, headers=headers)
                except Exception:
                    pass
                
                time.sleep(step_delay)
                
            print(f"🔊 Smooth fade complete: {target_volume}%")

        # ⚡ Run in a background thread so it doesn't freeze Vella's response time!
        threading.Thread(target=_fade, daemon=True).start()

    def next_track(self):
        """Skips to the next song."""
        headers = self._get_headers()
        if not headers: return
        requests.post(f"{self.base_url}/me/player/next", headers=headers)
        print("⏭️ Skipped to next track")

    def previous_track(self):
        """Goes back to the previous song."""
        headers = self._get_headers()
        if not headers: return
        requests.post(f"{self.base_url}/me/player/previous", headers=headers)
        print("⏮️ Went to previous track")

    def get_volco_device_id(self, headers):
        """Hunts down the Volco Headset in your Spotify device list."""
        import requests
        try:
            res = requests.get(f"{self.base_url}/me/player/devices", headers=headers)
            if res.status_code == 200:
                devices = res.json().get('devices', [])
                for d in devices:
                    # 🔍 DEBUG: Print out what Spotify actually sees
                    print(f"📱 Found Device: {d['name']} (Active: {d['is_active']})")
                    
                    # Look for "volco" in the name (case-insensitive)
                    if "volco" in d['name'].lower():
                        return d['id']
                
                # If Volco isn't found, fallback to any active device
                for d in devices:
                    if d['is_active']:
                        return d['id']
        except Exception as e:
            print(f"⚠️ Error fetching devices: {e}")
        return None

    def force_activate_headset(self):
        """Attempts to wake up and claim the Volco Headset on startup."""
        headers = self._get_headers()
        if not headers: return False

        print("📡 Volco OS: Attempting to claim Spotify playback...")

        # 🔥 STEP 1: Wake Spotify session
        try:
            requests.get(f"{self.base_url}/me/player", headers=headers)
        except:
            pass

        # 🔥 STEP 2: Discovery ping (your existing magic)
        self.discovery_ping()

        # 🔥 STEP 3: Retry to find device
        device_id = None
        for attempt in range(1):
            print(f"🔎 Searching for Volco device... Attempt {attempt+1}")
            device_id = self.get_volco_device_id(headers)
            if device_id:
                break
            time.sleep(1.5)

        if device_id:
            try:
                # 🔥 STEP 4: AGGRESSIVE TRANSFER (steal session from TV/phone/etc)
                for _ in range(3):
                    res = requests.put(
                        f"{self.base_url}/me/player",
                        headers=headers,
                        json={"device_ids": [device_id], "play": False}
                    )
                    if res.status_code in [200, 202, 204]:
                        print("✅ Volco Headset Linked & Ready.")
                        return True
                    time.sleep(1)

            except Exception as e:
                print(f"⚠️ Startup link failed: {e}")
        else:
            print("❌ Could not find Volco device. Open Spotify once to wake it up.")

        return False
    
    def control_playback(self, command):
        """Handles next, previous, pause, and resume."""
        import requests
        headers = self._get_headers()
        if not headers: return

        # Try to target Volco specifically, but fallback to any active session
        device_id = self.get_volco_device_id(headers)
        device_query = f"?device_id={device_id}" if device_id else ""

        endpoints = {
            "next": (requests.post, f"{self.base_url}/me/player/next{device_query}"),
            "previous": (requests.post, f"{self.base_url}/me/player/previous{device_query}"),
            "pause": (requests.put, f"{self.base_url}/me/player/pause{device_query}"),
            "resume": (requests.put, f"{self.base_url}/me/player/play{device_query}")
        }

        if command in endpoints:
            method, url = endpoints[command]
            res = method(url, headers=headers)
            if res.status_code in [200, 202, 204]:
                print(f"✅ Spotify: {command.capitalize()} executed.")
            else:
                print(f"❌ Spotify {command} failed: {res.status_code}")

    def search_and_play(self, query, search_type="track"):
        headers = self._get_headers()
        if not headers: return

        # Step 1: wake Volco session
        try: requests.get(f"{self.base_url}/me/player", headers=headers)
        except: pass

        # Step 2: find device
        target_device_id = None
        for attempt in range(5):
            print(f"🔎 Locating Volco... Attempt {attempt+1}")
            target_device_id = self.get_volco_device_id(headers)
            if target_device_id:
                break
            time.sleep(1.5)

        if not target_device_id:
            print("❌ Volco not found. Open Spotify and tap it once.")
            return

        # Step 3: search Spotify (limit=5 for better results)
        print(f"🔍 Searching Spotify for {search_type}: '{query}'...")
        safe_query = urllib.parse.quote(query)
        search_url = f"{self.base_url}/search?q={safe_query}&type={search_type}&limit=5"

        search_res = requests.get(search_url, headers=headers)
        if search_res.status_code != 200:
            print("❌ Search failed.")
            return

        data = search_res.json()
        items = []
        if search_type == "track": items = data.get("tracks", {}).get("items", [])
        if search_type == "album": items = data.get("albums", {}).get("items", [])
        if search_type == "playlist": items = data.get("playlists", {}).get("items", [])

        if not items:
            # fallback to track search if album/playlist fails
            if search_type in ["album", "playlist"]:
                print(f"⚠️ Couldn’t find {search_type} '{query}', trying track search...")
                self.search_and_play(query, search_type="track")
            else:
                print(f"⚠️ No {search_type} found for '{query}'.")
            return

        uri_to_play = items[0]["uri"]

        # Step 4: claim Volco device
        for _ in range(3):
            requests.put(
                f"{self.base_url}/me/player",
                headers=headers,
                json={"device_ids": [target_device_id], "play": False}
            )
            time.sleep(1)

        # Step 5: play
        payload = {"uris": [uri_to_play]} if search_type == "track" else {"context_uri": uri_to_play}
        play_url = f"{self.base_url}/me/player/play?device_id={target_device_id}"
        play_res = requests.put(play_url, headers=headers, json=payload)

        if play_res.status_code in [200, 202, 204]:
            print("✅ Playback started on Volco!")
        else:
            print(f"❌ Playback failed: {play_res.status_code} {play_res.text}")


        