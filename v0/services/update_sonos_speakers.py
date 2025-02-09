#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sonos.speakers import find_sonos_speakers
from sonos.cache import load_sonos_cache, save_sonos_cache

def update_sonos_cache():
    cache = load_sonos_cache()
    speakers = find_sonos_speakers()
    if speakers:
        for speaker in speakers:
            try:
                name = speaker.player_name
                cache[name] = speaker.ip_address
            except Exception as e:
                print(f"Skipping speaker at {speaker.ip_address}: {e}")
        save_sonos_cache(cache)
    return list(cache.keys())

if __name__ == "__main__":
    updated = update_sonos_cache()
    if updated:
        print("Updated Sonos speakers cache:", ", ".join(updated))
    else:
        print("No Sonos speakers discovered.")