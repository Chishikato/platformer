"""
RoomScanner for LAN game discovery via UDP broadcast.
"""
import socket

from config.constants import DISCOVERY_PORT, DISCOVERY_MSG, MODE_VERSUS


class RoomScanner:
    def __init__(self):
        self.found_hosts = {}  # Changed to dict: {ip: mode}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try: self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except: pass
        self.sock.setblocking(False)
        try: self.sock.bind(("", DISCOVERY_PORT))
        except: pass
        self.broadcast_mode = MODE_VERSUS  # Store mode to broadcast
    
    def broadcast(self, mode=None):
        if mode:
            self.broadcast_mode = mode
        # Send mode with discovery message
        msg = DISCOVERY_MSG + b":" + self.broadcast_mode.encode('utf-8')
        try: self.sock.sendto(msg, ("<broadcast>", DISCOVERY_PORT))
        except: pass

    def listen(self):
        try:
            while True:
                data, addr = self.sock.recvfrom(1024)
                if data.startswith(DISCOVERY_MSG):
                    # Parse mode from message
                    try:
                        parts = data.decode('utf-8').split(':')
                        mode = parts[1] if len(parts) > 1 else MODE_VERSUS
                    except:
                        mode = MODE_VERSUS
                    self.found_hosts[addr[0]] = mode
        except BlockingIOError: pass
        except Exception: pass
