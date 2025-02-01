from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import threading
from utilities.network import get_local_ip  # Assuming you have a utilities module

class AudioServer:
    def __init__(self, port=8009):
        self.port = port
        self.audio_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "v0/audio_cache")
        os.makedirs(self.audio_dir, exist_ok=True)
        
        self.handler = SimpleHTTPRequestHandler
        self.handler.directory = self.audio_dir
        self.server = None
        
    def start(self):
        local_ip = get_local_ip()
        self.server = HTTPServer((local_ip, self.port), self.handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        print(f"Audio server running on http://{local_ip}:{self.port}/")
        
    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            
    def get_url_for_file(self, filename):
        return f"http://localhost:{self.port}/{filename}"

if __name__ == "__main__":
    server = AudioServer()
    server.start()
    
    try:
        # Keep main thread alive
        while True:
            input()
    except KeyboardInterrupt:
        server.stop() 