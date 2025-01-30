import http.server
import socketserver
import threading
import os
from pathlib import Path

class AudioServer:
    def __init__(self, port=8000):
        self.port = port
        # Use absolute path from project root
        self.audio_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audio_cache")
        os.makedirs(self.audio_dir, exist_ok=True)
        self.server = None
        os.chdir(self.audio_dir)  # Change directory once at startup
        self.start_server()

    def start_server(self):
        handler = http.server.SimpleHTTPRequestHandler
        self.server = socketserver.TCPServer(("0.0.0.0", self.port), handler)
        server_thread = threading.Thread(target=self.server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        print(f"HTTP server running on port {self.port}")

    def get_url_for_file(self, filepath: str) -> str:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't actually connect, just gets local interface IP
            s.connect(('8.8.8.8', 1))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = '127.0.0.1'
        finally:
            s.close()
        return f"http://{local_ip}:{self.port}/{os.path.basename(filepath)}"

    def copy_file_to_server(self, source_path: str) -> str:
        import shutil
        import uuid
        
        # Generate unique filename
        ext = os.path.splitext(source_path)[1]
        new_filename = f"{uuid.uuid4()}{ext}"
        dest_path = os.path.join(self.audio_dir, new_filename)
        
        # Copy file to server directory
        shutil.copy2(source_path, dest_path)
        return new_filename

# Global server instance
audio_server = AudioServer() 