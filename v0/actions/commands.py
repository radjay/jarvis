import subprocess
import json

def open_garage_door():
    try:
        subprocess.run(["shortcuts", "run","HomeKit-Open-Garage-Door"], check=True)
        return "The garage door has been opened."
    except subprocess.CalledProcessError as e:
        return f"Failed to open the garage door: {e}"

AVAILABLE_FUNCTIONS = {
    "open_garage_door": open_garage_door,
}

def dispatch_function_call(function_call):
    fname = function_call.get("name")
    fn = AVAILABLE_FUNCTIONS.get(fname)
    if not fn:
        return f"Function '{fname}' is not implemented."
    arguments = function_call.get("arguments")
    try:
        args = json.loads(arguments) if arguments else {}
    except Exception:
        args = {}
    return fn(**args) if args else fn()