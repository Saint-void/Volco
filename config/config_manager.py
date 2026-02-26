import json
import os

# Get the absolute path to settings.json
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "settings.json")

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: Could not find {CONFIG_PATH}")
        exit(1)

# We create a global config object that other files will import
config = load_config()