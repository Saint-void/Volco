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
        """Resumes current playback."""
        headers = self._get_headers()
        if not headers: return
        requests.put(f"{self.base_url}/me/player/play", headers=headers)
        print("▶️ Playing/Resuming music")

    def pause(self):
        """Pauses current playback."""
        headers = self._get_headers()
        if not headers: return
        requests.put(f"{self.base_url}/me/player/pause", headers=headers)
        print("⏸️ Paused music")

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
        for attempt in range(5):
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

        # 🔥 STEP 1: Wake Spotify session
        try:
            requests.get(f"{self.base_url}/me/player", headers=headers)
        except:
            pass

        # 🔥 STEP 2: Find device with retry
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

        # 🔍 STEP 3: SEARCH
        print(f"🔍 Searching Spotify for {search_type}: '{query}'...")
        safe_query = urllib.parse.quote(query)
        search_url = f"{self.base_url}/search?q={safe_query}&type={search_type}&limit=1"

        search_res = requests.get(search_url, headers=headers)
        if search_res.status_code != 200:
            print("❌ Search failed.")
            return

        data = search_res.json()
        uri_to_play = None

        try:
            if search_type == "track":
                uri_to_play = data["tracks"]["items"][0]["uri"]
            elif search_type == "album":
                uri_to_play = data["albums"]["items"][0]["uri"]
            elif search_type == "playlist":
                uri_to_play = data["playlists"]["items"][0]["uri"]
        except IndexError:
            print(f"⚠️ No {search_type} found for '{query}'.")
            return

        if uri_to_play:
            print("🎯 Found track. Taking over playback...")

            # 🔥 STEP 4: AGGRESSIVE TRANSFER (steal from TV/phone)
            for _ in range(3):
                requests.put(
                    f"{self.base_url}/me/player",
                    headers=headers,
                    json={"device_ids": [target_device_id], "play": False}
                )
                time.sleep(1)

            # 🔥 STEP 5: PLAY
            payload = {"uris": [uri_to_play]} if search_type == "track" else {"context_uri": uri_to_play}
            play_url = f"{self.base_url}/me/player/play?device_id={target_device_id}"

            play_res = requests.put(play_url, headers=headers, json=payload)

            if play_res.status_code in [200, 202, 204]:
                print("✅ Playback started on Volco!")
            else:
                print(f"❌ Playback failed: {play_res.status_code} {play_res.text}")
            
            # ⚡ THE DJ AUTOPLAY FIX (Corrected)
            if search_type == "track":
                track_id = uri_to_play.split(":")[-1] # Extract just the ID
                print("🎧 DJ Volco: Fetching similar songs to keep the vibe going...")
                
                # Ask Spotify for 3 recommended tracks based on this song
                rec_url = f"{self.base_url}/recommendations?seed_tracks={track_id}&limit=3"
                rec_res = requests.get(rec_url, headers=headers)
                
                if rec_res.status_code == 200:
                    recommended_tracks = rec_res.json().get('tracks', [])
                    for t in recommended_tracks:
                        # Add each to the queue
                        q_url = f"{self.base_url}/me/player/queue?uri={t['uri']}"
                        
                        # ⚡ FIXED: Using target_device_id
                        if target_device_id: 
                            q_url += f"&device_id={target_device_id}"
                            
                        requests.post(q_url, headers=headers)
                    print("✅ Queue loaded with similar tracks!")