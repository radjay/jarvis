import os
import json
import time
import soco
from soco.snapshot import Snapshot

import requests
from .cache import load_sonos_cache, save_sonos_cache
from utilities import get_local_ip  # Changed from relative import
from dotenv import load_dotenv

load_dotenv()
DEFAULT_SONOS_SPEAKER_IP = os.getenv("SONOS_SPEAKER_IP")

def get_sonos_speaker(room_name=None):
    cache = load_sonos_cache()
    if room_name:
        ip = cache.get(room_name)
        if not ip:
            raise ValueError(f"No IP found for room: {room_name}")
        try:
            speaker = soco.SoCo(ip)
            _ = speaker.player_name  # Verify connectivity
            return speaker
        except Exception as e:
            print(f"Failed to connect to Sonos speaker {room_name} at {ip}: {e}")
            # Optionally, remove from cache
            del cache[room_name]
            save_sonos_cache(cache)
            raise
    else:
        # If no room_name provided, connect to default or first available speaker
        if cache:
            room_name, ip = next(iter(cache.items()))
            try:
                speaker = soco.SoCo(ip)
                _ = speaker.player_name
                return speaker
            except Exception as e:
                print(f"Failed to connect to Sonos speaker {room_name} at {ip}: {e}")
                del cache[room_name]
                save_sonos_cache(cache)
        # Attempt discovery
        discovery = soco.discover(timeout=10)
        if discovery:
            for speaker in discovery:
                try:
                    print(f"Discovered Speaker: {speaker.player_name}, IP: {speaker.ip_address}")
                    cache[speaker.player_name] = speaker.ip_address
                    save_sonos_cache(cache)
                    return speaker
                except Exception as e:
                    print(f"Failed to process discovered speaker at {speaker.ip_address}: {e}")
        # Fallback to default IP
        if DEFAULT_SONOS_SPEAKER_IP:
            try:
                speaker = soco.SoCo(DEFAULT_SONOS_SPEAKER_IP)
                _ = speaker.player_name
                cache[speaker.player_name] = DEFAULT_SONOS_SPEAKER_IP
                save_sonos_cache(cache)
                return speaker
            except Exception as e:
                print(f"Failed to connect to default Sonos speaker at {DEFAULT_SONOS_SPEAKER_IP}: {e}")
        raise Exception("No Sonos speakers available.")

def play_on_sonos(audio_file_path: str, room_name: str = None):
    from soco.exceptions import SoCoUPnPException
    try:
        speaker = get_sonos_speaker(room_name)
    except Exception as e:
        print(f"Could not find speaker: {e}")
        raise

    print(f"Selected speaker: {speaker.player_name} ({speaker.ip_address})")

    local_ip = get_local_ip()
    sonos_url = f"http://{local_ip}:8009/v0/audio_cache/{audio_file_path}"

    try:
        response = requests.get(sonos_url)
        response.raise_for_status()  # ensure proper HTTP response
    except requests.exceptions.RequestException as err:
        print("Error playing on Sonos: Audio server isn't running")
        return
    print(f"Using audio URL: {sonos_url}")

    try:
        test_response = requests.get(sonos_url)
        print(f"URL test status: {test_response.status_code}")
        if test_response.status_code != 200:
            raise Exception(f"Audio URL not accessible: {sonos_url}")

        # Capture current volume and speaker state.
        orig_volume = speaker.volume
        # Calculate a ducked volume (for background). 
        duck_volume = int(orig_volume * 0.5)  # e.g. 50% of original.
        print(f"Ducking background volume from {orig_volume} to {duck_volume}")

        snap = Snapshot(speaker)
        snap.snapshot()
        speaker.volume = duck_volume

        # Optional: Pre-amplify your TTS file here so it sounds louder than the ducked background.
        print(f"Sending TTS to Sonos {speaker.player_name}")
        speaker.add_uri_to_queue(sonos_url, 0)
        speaker.play_from_queue(0)

        while True:
            state = speaker.get_current_transport_info()['current_transport_state']
            if state == 'STOPPED':
                break
            time.sleep(0.5)

        try:
            print("Clearing TTS message from queue")
            speaker.clear_queue()
        except Exception as e:
            print("Error clearing queue:", e)

    except SoCoUPnPException as e:
        print(f"UPnP error: {e}")
        raise
    except Exception as e:
        print(f"Error playing on Sonos: {e}")
        raise
    finally:
        if 'orig_volume' in locals():
            try:
                print("Restoring original volume")
                speaker.volume = orig_volume
            except Exception as e:
                print("Error restoring volume:", e)
        if 'snap' in locals():
            try:
                print("Restoring previous speaker state")
                snap.restore(fade=True)
                if speaker.get_current_transport_info().get('current_transport_state') != 'PLAYING':
                    print("Resuming playback")
                    speaker.play()
            except Exception as e:
                print("Error restoring snapshot:", e)

def find_sonos_speakers():
    discovery = soco.discover(timeout=10)
    if discovery:
        return list(discovery)
    return [] 