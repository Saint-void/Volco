import json
import os
import base64
import requests

# ⚡ YOUR SPOTIFY APP CREDENTIALS
CLIENT_ID = "ab7f761ecf374d629e3674d014674dd1"
CLIENT_SECRET = "65742ae20dac40e7ba963f151412a2b8" 

def get_fresh_token():
    print("🔄 Generating fresh Access Token from the Master Key...")
    # 1. Read the token your phone beamed over
    creds_path = os.path.expanduser("~/volco_spotify_creds.json")
    with open(creds_path, "r") as f:
        data = json.load(f)
        refresh_token = data.get("refresh_token")

    # 2. Ask Spotify for a new 60-minute pass
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth_str}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    response = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=payload)
    
    if response.status_code == 200:
        print("✅ Access Token acquired!")
        return response.json().get("access_token")
    else:
        print("❌ Failed to get token:", response.text)
        return None

def trigger_standalone_playback():
    token = get_fresh_token()
    if not token: return

    headers = { "Authorization": f"Bearer {token}" }

    print("🔍 Looking for the Volco Headset hardware...")
    # Fetch all active Spotify devices on your account
    res = requests.get("https://api.spotify.com/v1/me/player/devices", headers=headers)
    devices = res.json().get("devices", [])

    volco_id = None
    for d in devices:
        if "Volco" in d.get("name", ""):
            volco_id = d.get("id")

    if volco_id:
        print(f"🎯 Target Acquired! Forcing playback on Volco Headset (ID: {volco_id})")
        
        # ⚡ THE MAGIC COMMAND: Tell Spotify to play music directly out of the Pi!
        # We'll just resume whatever was playing last, or play a default playlist
        play_res = requests.put(f"https://api.spotify.com/v1/me/player/play?device_id={volco_id}", headers=headers)
        
        if play_res.status_code in [200, 204]:
            print("🎶 BOOM! The headset is playing music by itself!")
        else:
            print("⚠️ Spotify error:", play_res.text)
    else:
        print("💤 The Volco Headset is asleep. Play a song from the Volco app once to wake it up on Spotify's servers!")

if __name__ == "__main__":
    trigger_standalone_playback()