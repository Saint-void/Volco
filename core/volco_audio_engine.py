import json
import os
import base64
import requests
import urllib.parse

# ⚡ YOUR SPOTIFY APP CREDENTIALS
CLIENT_ID = "ab7f761ecf374d629e3674d014674dd1"
CLIENT_SECRET = "65742ae20dac40e7ba963f151412a2b8"

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

    def search_and_play(self, query, search_type="track"):
        """Searches for media and forces playback onto Volco Headset."""
        import urllib.parse
        import requests

        headers = self._get_headers()
        if not headers: return

        # --- 1. FIND & WAKE UP VOLCO HEADSET ---
        target_device_id = self.get_volco_device_id(headers)

        if not target_device_id:
            print("❌ Could not find Volco Headset on Spotify's network. Try opening Spotify on your phone and selecting it once to wake it up.")
            return

        # --- 2. SEARCH SPOTIFY ---
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
            print(f"⚠️ Couldn't find any {search_type} matching '{query}'.")
            return

        # --- 3. FORCE PLAYBACK ---
        if uri_to_play:
            print(f"🎯 Found it! URI: {uri_to_play}. Transferring stream to Volco Headset...")
            
            # ⚡ THE WAKE-UP CALL: Transfer playback to Volco Headset first
            transfer_payload = {"device_ids": [target_device_id], "play": False}
            requests.put(f"{self.base_url}/me/player", headers=headers, json=transfer_payload)
            
            # ⚡ THE PLAY COMMAND
            payload = {"uris": [uri_to_play]} if search_type == "track" else {"context_uri": uri_to_play}
            play_url = f"{self.base_url}/me/player/play?device_id={target_device_id}"
            
            play_res = requests.put(play_url, headers=headers, json=payload)
            
            if play_res.status_code in [200, 202, 204]:
                print("✅ Playback started successfully on Volco Headset!")
            else:
                print(f"❌ Playback failed with status {play_res.status_code}: {play_res.text}")