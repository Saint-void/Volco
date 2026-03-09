import subprocess

# ⚡ VOLCO'S SHORT-TERM MEMORY
# This remembers if music was actually playing before the AI woke up
_was_playing = False

def pause_media():
    """Checks if music is playing, pauses it, and remembers the state."""
    global _was_playing
    _was_playing = False # Reset memory for the new session
    
    try:
        # Ask Linux what the current media status is (Playing, Paused, or Stopped)
        result = subprocess.run(["playerctl", "status"], capture_output=True, text=True, check=False)
        status = result.stdout.strip()
        
        if status == "Playing":
            print("⏸️  [BT MODE] Music is playing. Pausing for Vella...")
            _was_playing = True
            subprocess.run(["playerctl", "pause"], check=False, stderr=subprocess.DEVNULL)
        else:
            print(f"⏸️  [BT MODE] Media is {status or 'Stopped'}. Leaving it alone.")
            
    except Exception as e:
        print(f"⚠️ [BT MODE] Pause check failed: {e}")

def resume_media():
    """Only resumes music if Volco was the one who interrupted it."""
    global _was_playing
    
    if _was_playing:
        print("▶️  [BT MODE] Conversation over. Resuming music...")
        try:
            subprocess.run(["playerctl", "play"], check=False, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"⚠️ [BT MODE] Resume failed: {e}")
    else:
        print("▶️  [BT MODE] Music wasn't playing before. Staying quiet.")
        
    # Wipe the memory clean for the next time
    _was_playing = False