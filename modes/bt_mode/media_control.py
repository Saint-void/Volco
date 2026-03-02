import time
import platform
import ctypes
import asyncio

# ⚡ MEMORY: Volco will remember if it was the one who interrupted the music
_was_playing_before_hijack = False

def is_windows_music_playing():
    """Asks the Windows OS if any app (Spotify, Chrome) is currently playing audio."""
    try:
        from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager
        
        async def get_state():
            sessions = await MediaManager.request_async()
            current_session = sessions.get_current_session()
            if current_session:
                info = current_session.get_playback_info()
                # ⚡ THE FIX: Ensure 'info' isn't None before checking its status
                if info: 
                    return info.playback_status == 4  
            return False
            
        return asyncio.run(get_state())
    except ImportError:
        print("⚠️ [BT MODE] 'winsdk' not installed. Falling back to blind toggle.")
        return True 
    except Exception as e:
        return False # ⚡ Default to False on any weird OS errors so we don't accidentally play music

def toggle_media():
    """Sends the raw OS hardware code to press the Play/Pause button."""
    VK_MEDIA_PLAY_PAUSE = 0xB3
    ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 2, 0)

def pause_media():
    """Smart pause: Only pauses if music is actually playing."""
    global _was_playing_before_hijack
    print("⏸️  [BT MODE] Checking media state...")
    
    if platform.system() == "Windows":
        _was_playing_before_hijack = is_windows_music_playing()
        
        if _was_playing_before_hijack:
            print("⏸️  [BT MODE] Music is playing. Pausing now...")
            toggle_media()
        else:
            print("⏸️  [BT MODE] Silence detected. Leaving media alone.")
    else:
        # ⚡ For the Raspberry Pi: We use an explicit 'pause' command, not a toggle!
        import subprocess
        _was_playing_before_hijack = True 
        subprocess.run(["playerctl", "pause"], check=False, stderr=subprocess.DEVNULL)
        
    time.sleep(0.5)

def resume_media():
    """Smart resume: Only plays if Volco was the one who paused it."""
    global _was_playing_before_hijack
    
    if not _was_playing_before_hijack:
        print("▶️  [BT MODE] Music was paused before we started. Leaving it paused.")
        return
        
    print("▶️  [BT MODE] Conversation over. Resuming music...")
    if platform.system() == "Windows":
        toggle_media()
    else:
        # ⚡ For the Raspberry Pi: Explicit 'play' command
        import subprocess
        subprocess.run(["playerctl", "play"], check=False, stderr=subprocess.DEVNULL)
    
    time.sleep(0.5)
    # Wipe the memory for the next interaction
    _was_playing_before_hijack = False