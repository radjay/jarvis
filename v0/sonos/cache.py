import os
import json

CACHE_FILE = "sonos_cache.json"

def load_sonos_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_sonos_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)
