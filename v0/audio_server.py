from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import threading
import pyaudio
import socket
from utilities.network import get_local_ip
from enum import Enum
import time

class AudioMode(Enum):
    FILE = "file"
    STREAM = "stream"
    BOTH = "both"

class AudioServer:
    def __init__(self, mode=AudioMode.BOTH, file_port=8009, stream_port=12345):
        self.mode = mode
        self.file_port = file_port
        self.stream_port = stream_port
        
        # File mode settings
        self.audio_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "v0/audio_cache")
        os.makedirs(self.audio_dir, exist_ok=True)
        
        # Stream mode settings
        self.CHUNK = 4096
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100
        self.clients = []
        self.play_audio = False
        self.audio = None
        self.output_stream = None
        
        # Server instances
        self.file_server = None
        self.stream_server = None
        self.threads = []
        
        self.publishers = []
        self.subscribers = []
        
    def start(self):
        if self.mode in [AudioMode.FILE, AudioMode.BOTH]:
            self._start_file_server()
        if self.mode in [AudioMode.STREAM, AudioMode.BOTH]:
            self._start_stream_server()
            
    def _start_file_server(self):
        local_ip = get_local_ip()
        handler = SimpleHTTPRequestHandler
        handler.directory = self.audio_dir
        self.file_server = HTTPServer((local_ip, self.file_port), handler)
        file_thread = threading.Thread(target=self.file_server.serve_forever)
        file_thread.daemon = True
        file_thread.start()
        self.threads.append(file_thread)
        print(f"File audio server running on http://{local_ip}:{self.file_port}/")
        
    def _start_stream_server(self):
        # Initialize PyAudio
        self.audio = pyaudio.PyAudio()
        
        # Create and start server
        local_ip = get_local_ip()
        self.stream_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.stream_server.bind((local_ip, self.stream_port))
        self.stream_server.listen(5)
        
        print(f"Streaming audio server running on {local_ip}:{self.stream_port}")
        print("Press 'p' to toggle audio playback")
        print("Press 'q' to quit")
        
        # Start keyboard input thread
        input_thread = threading.Thread(target=self._handle_keyboard_input)
        input_thread.daemon = True
        input_thread.start()
        self.threads.append(input_thread)
        
        # Start client handling thread
        stream_thread = threading.Thread(target=self._handle_stream_connections)
        stream_thread.daemon = True
        stream_thread.start()
        self.threads.append(stream_thread)
        
    def _handle_stream_connections(self):
        try:
            while True:
                client_socket, address = self.stream_server.accept()
                # Read role marker (3 bytes)
                role = client_socket.recv(3)
                if role == b"PUB":
                    print(f"Publisher connected from {address}")
                    self.publishers.append(client_socket)
                    threading.Thread(target=self._handle_publisher, args=(client_socket, address), daemon=True).start()
                elif role == b"SUB":
                    print(f"Subscriber connected from {address}")
                    self.subscribers.append(client_socket)
                    threading.Thread(target=self._handle_subscriber, args=(client_socket, address), daemon=True).start()
                else:
                    print(f"Unknown role from {address}, closing connection")
                    client_socket.close()
        except Exception as e:
            print(f"Server error: {str(e)}")
            
    def _handle_publisher(self, client_socket, address):
        try:
            while True:
                data = client_socket.recv(self.CHUNK * 2)
                if not data:
                    break
                # Write to local audio output if playback is enabled
                if self.play_audio and self.output_stream:
                    try:
                        self.output_stream.write(data)
                    except Exception as e:
                        print(f"Error playing audio: {e}")
                # Broadcast to all subscribers
                for sub in self.subscribers:
                    try:
                        sub.sendall(data)
                    except Exception as e:
                        print(f"Error sending to subscriber: {e}")
            print(f"Publisher disconnected {address}")
        except Exception as e:
            print(f"Error handling publisher {address}: {e}")
        finally:
            if client_socket in self.publishers:
                self.publishers.remove(client_socket)
            client_socket.close()
            
    def _handle_subscriber(self, client_socket, address):
        try:
            while True:
                # Just keep the connection alive so broadcasts can be sent.
                time.sleep(1)
        except Exception as e:
            print(f"Error in subscriber {address}: {e}")
        finally:
            if client_socket in self.subscribers:
                self.subscribers.remove(client_socket)
            client_socket.close()
            print(f"Subscriber {address} disconnected")
            
    def _handle_keyboard_input(self):
        while True:
            cmd = input().lower()
            if cmd == 'p':
                self.toggle_playback()
            elif cmd == 'q':
                self.stop()
                break
                
    def toggle_playback(self):
        self.play_audio = not self.play_audio
        print(f"Audio playback {'enabled' if self.play_audio else 'disabled'}")
        
        if self.play_audio and not self.output_stream:
            self.output_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK
            )
        elif not self.play_audio and self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
            self.output_stream = None
            
    def stop(self):
        if self.file_server:
            self.file_server.shutdown()
            self.file_server.server_close()
            
        if self.stream_server:
            self.stream_server.close()
            
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
        if self.audio:
            self.audio.terminate()
            
    def get_url_for_file(self, filename):
        if self.mode == AudioMode.STREAM:
            raise RuntimeError("get_url_for_file() is only available in FILE or BOTH modes")
        return f"http://localhost:{self.file_port}/{filename}"

if __name__ == "__main__":
    import sys
    mode = AudioMode.BOTH  # Default to running both servers
    if len(sys.argv) > 1:
        mode = AudioMode[sys.argv[1].upper()]
    server = AudioServer(mode=mode)
    server.start()
    
    try:
        while True:
            if mode == AudioMode.FILE:
                input()  # Keep main thread alive for file server only
            else:
                time.sleep(1)  # Keep main thread alive while allowing keyboard input
    except KeyboardInterrupt:
        server.stop() 