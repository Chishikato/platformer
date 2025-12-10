"""
NetworkManager class for multiplayer game networking.
Handles TCP connections for game state synchronization between host and client.
"""
import socket
import threading
import time
import select

from config.constants import (
    ROLE_LOCAL_ONLY, ROLE_HOST, ROLE_CLIENT, MODE_VERSUS
)
from .room_scanner import RoomScanner


class NetworkManager:
    def __init__(self):
        self.role = ROLE_LOCAL_ONLY
        self.sock = None
        self.connected = False
        self.lock = threading.Lock()
        # Added action, frame_index, and invul_timer to remote state
        self.remote_state = {
            "x": 0.0, "y": 0.0, "alive": True, "score": 0, "seed": 0, 
            "hp": 3, "vx": 0.0, "vy": 0.0, "facing_right": True,
            "max_hp": 3, "slam_active": 0, "dash_active": 0,
            "action": "idle", "frame": 0
        }
        self.remote_lobby_mode = None
        self.remote_enemy_updates = []  # List of (index, hp, is_dead)
        self._recv_buffer = ""
        self.remote_game_over = False
        self.remote_winner_text = ""
        self.remote_start_triggered = False 
        self.remote_lobby_exit = False 
        self.scanner = RoomScanner()
        self.broadcasting = False
        self.hosting = False 
        self.server_socket = None
        self.remote_char_color = 3 
        self.remote_char_ability = 0 
        self.remote_hits = []
        self.damage_received_queue = 0  # Accumulated damage to apply to local player
        
        # Enhanced Boss State
        self.remote_boss_state = {
            "hp": 5, "dead": False, "x": 0, "y": 0, "action": "idle", "frame": 0, "active": False
        }

    def close(self):
        self.hosting = False 
        self.connected = False
        self.broadcasting = False
        self.remote_lobby_mode = None
        self.remote_start_triggered = False
        if self.sock:
            try: self.sock.close()
            except: pass
        self.sock = None
        if self.server_socket:
            try: self.server_socket.close()
            except: pass
        self.server_socket = None
        self.role = ROLE_LOCAL_ONLY
        self.remote_game_over = False

    def reset_connection_only(self):
        if self.sock:
            try: self.sock.close()
            except: pass
        self.sock = None
        self.connected = False
        self.broadcasting = True
        self.remote_state["alive"] = True
        self._recv_buffer = ""
        with self.lock:
            self.remote_boss_state["active"] = False

    def start_broadcast_thread(self):
        self.broadcasting = True
        def broadcast_loop():
            while self.hosting:
                if self.broadcasting and not self.connected: 
                    self.scanner.broadcast(self.remote_lobby_mode or MODE_VERSUS)
                time.sleep(1.0)
        t = threading.Thread(target=broadcast_loop, daemon=True)
        t.start()

    def host(self, port=50007):
        self.close()
        self.role = ROLE_HOST
        self.hosting = True
        self.start_broadcast_thread()
        def server_thread():
            try:
                srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                srv.bind(("", port))
                srv.listen(1)
                srv.setblocking(False)
                self.server_socket = srv
                while self.hosting:
                    if not self.connected:
                        try:
                            readable, _, _ = select.select([srv], [], [], 0.5)
                            if srv in readable:
                                conn, _ = srv.accept()
                                conn.setblocking(False)
                                with self.lock:
                                    self.sock = conn
                                    self.connected = True
                                    self.broadcasting = False 
                        except: pass
                    else:
                        time.sleep(0.2)
                srv.close()
            except: self.close()
        t = threading.Thread(target=server_thread, daemon=True)
        t.start()

    def join(self, host_ip, port=50007):
        self.close()
        self.role = ROLE_CLIENT
        def client_thread():
            try:
                conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                conn.connect((host_ip, port))
                conn.setblocking(False)
                self.sock = conn
                self.connected = True
            except: self.close()
        t = threading.Thread(target=client_thread, daemon=True)
        t.start()

    def send_local_state(self, px, py, alive, score, seed, hp, vx, vy, facing_right, max_hp, slam_active, dash_active, invul_timer, flash_on_invul, action, frame):
        if not self.connected or not self.sock: return
        slam_int = 1 if slam_active else 0
        dash_int = 1 if dash_active else 0
        facing_int = 1 if facing_right else 0
        alive_int = 1 if alive else 0
        flash_int = 1 if flash_on_invul else 0
        
        line = f"{px:.2f},{py:.2f},{alive_int},{int(score)},{int(seed)},{int(hp)},{vx:.2f},{vy:.2f},{facing_int},{int(max_hp)},{slam_int},{dash_int},{invul_timer:.2f},{flash_int}|{action},{int(frame)}\n"
        
        try: 
            self.sock.sendall(line.encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError):
            print("Network Error: Pipe Broken")
            self.close()
        except BlockingIOError:
            pass
        except Exception as e:
            print(f"Send Error: {e}")
            self.close()
    
    def send_hit(self, enemy_id, damage):
        """Send a packet telling the host we hit an enemy"""
        if self.connected:
            try:
                msg = f"H|{int(enemy_id)},{float(damage)}\n"
                self.sock.sendall(msg.encode("utf-8"))
            except: pass

    def send_damage_to_client(self, amount):
        """Host tells client they took damage (from boss/traps)"""
        if self.connected and self.role == ROLE_HOST:
            try:
                msg = f"D|{int(amount)}\n"
                self.sock.sendall(msg.encode("utf-8"))
            except: pass

    def check_damage_received(self):
        """Retrieve damage sent by Host"""
        with self.lock:
            amt = self.damage_received_queue
            self.damage_received_queue = 0
            return amt

    def get_remote_hits(self):
        """Retrieve and clear the list of hits sent by the client"""
        with self.lock:
            hits = self.remote_hits[:]
            self.remote_hits.clear()
            return hits

    def send_game_over(self, text):
        if self.connected: self.sock.sendall(f"G|{text}\n".encode("utf-8"))

    def send_lobby_mode(self, mode):
        if self.connected: self.sock.sendall(f"M|{mode}\n".encode("utf-8"))

    def send_start_game(self):
        if self.connected: self.sock.sendall(b"S|START\n")
    
    def send_kick(self):
        if self.connected: self.sock.sendall(b"K|KICK\n")
    
    def send_char_selection(self, color_index, ability_index):
        if self.connected: self.sock.sendall(f"C|{color_index},{ability_index}\n".encode("utf-8"))
    
    def send_enemy_update(self, index, x, y, facing_right, hp, is_dead):
        if self.connected: 
            dead_int = 1 if is_dead else 0
            face_int = 1 if facing_right else 0
            msg = f"E|{index},{int(x)},{int(y)},{face_int},{int(hp)},{dead_int}\n"
            try:
                self.sock.sendall(msg.encode("utf-8"))
            except (BrokenPipeError, ConnectionResetError):
                self.close()
            except BlockingIOError:
                pass
            except Exception:
                pass
    
    def send_boss_state(self, hp, boss_defeated, x, y, action, frame):
        if self.connected:
            def_int = 1 if boss_defeated else 0
            line = f"B|{int(hp)},{def_int},{int(x)},{int(y)}|{action},{int(frame)}\n"
            self.sock.sendall(line.encode("utf-8"))
    
    def send_lobby_exit(self):
        if self.connected: self.sock.sendall(b"L|EXIT\n")

    def poll_remote_state(self):
        if not self.sock: return
        try:
            data = self.sock.recv(4096)
            if not data: raise ConnectionResetError()
            self._recv_buffer += data.decode("utf-8")
        except (BlockingIOError, socket.timeout): return
        except Exception:
            with self.lock:
                if self.role == ROLE_HOST: self.reset_connection_only()
                else: self.close()
            return

        while "\n" in self._recv_buffer:
            line, self._recv_buffer = self._recv_buffer.split("\n", 1)
            if not line: continue
            
            if line.startswith("K|"):
                with self.lock: self.close()
                continue
            if line.startswith("G|"):
                with self.lock:
                    self.remote_game_over = True
                    self.remote_winner_text = line[2:]
                continue
            if line.startswith("M|"):
                with self.lock: self.remote_lobby_mode = line[2:].strip()
                continue
            if line.startswith("S|"):
                with self.lock: self.remote_start_triggered = True
                continue
            
            if line.startswith("D|"):
                try:
                    amt = int(line[2:])
                    with self.lock:
                        self.damage_received_queue += amt
                except: pass
                continue

            if line.startswith("C|"):
                try:
                    parts = line[2:].strip().split(",")
                    if len(parts) == 2:
                        with self.lock:
                            self.remote_char_color = int(parts[0])
                            self.remote_char_ability = int(parts[1])
                except: pass
                continue

            if line.startswith("H|"):
                try:
                    parts = line[2:].strip().split(",")
                    if len(parts) >= 2:
                        eid = int(parts[0])
                        dmg = float(parts[1])
                        with self.lock:
                            self.remote_hits.append((eid, dmg))
                except: pass
                continue
            
            if line.startswith("E|"):
                try:
                    parts = line[2:].strip().split(",")
                    if len(parts) >= 6:
                        idx = int(parts[0])
                        ex = int(parts[1])
                        ey = int(parts[2])
                        facing = bool(int(parts[3]))
                        hp = int(parts[4])
                        dead = bool(int(parts[5]))
                        with self.lock: 
                            self.remote_enemy_updates.append((idx, ex, ey, facing, hp, dead))
                except: pass
                continue
            
            if line.startswith("B|"):
                try:
                    main_split = line[2:].split("|")
                    stats = main_split[0].split(",")
                    
                    with self.lock:
                        self.remote_boss_state["active"] = True
                        self.remote_boss_state["hp"] = int(stats[0])
                        self.remote_boss_state["dead"] = bool(int(stats[1]))
                        if len(stats) > 3:
                            self.remote_boss_state["x"] = int(stats[2])
                            self.remote_boss_state["y"] = int(stats[3])
                        
                        if len(main_split) > 1:
                            anim_data = main_split[1].split(",")
                            self.remote_boss_state["action"] = anim_data[0]
                            self.remote_boss_state["frame"] = int(anim_data[1])
                except: pass
                continue

            if line.startswith("L|"):
                with self.lock: self.remote_lobby_exit = True
                continue
            
            # Player State Parsing
            main_parts = line.split("|")
            stats_str = main_parts[0]
            anim_str = main_parts[1] if len(main_parts) > 1 else "idle,0"
            
            parts = stats_str.split(",")
            if len(parts) < 13: continue 
            try:
                rx, ry = float(parts[0]), float(parts[1])
                alive, score = bool(int(parts[2])), int(parts[3])
                r_seed = int(parts[4]) if len(parts) > 4 else 0
                r_hp = int(parts[5]) if len(parts) > 5 else 3
                r_vx = float(parts[6]) if len(parts) > 6 else 0.0
                r_vy = float(parts[7]) if len(parts) > 7 else 0.0
                r_facing = bool(int(parts[8])) if len(parts) > 8 else True
                r_max_hp = int(parts[9]) if len(parts) > 9 else 3
                r_slam = bool(int(parts[10])) if len(parts) > 10 else False
                r_dash = bool(int(parts[11])) if len(parts) > 11 else False
                r_invul = float(parts[12]) if len(parts) > 12 else 0.0
                r_flash = bool(int(parts[13])) if len(parts) > 13 else False
                
                aparts = anim_str.split(",")
                r_action = aparts[0]
                r_frame = int(aparts[1]) if len(aparts) > 1 else 0

                with self.lock:
                    self.remote_state.update({
                        "x": rx, "y": ry, "alive": alive, "score": score, 
                        "seed": r_seed, "hp": r_hp, "vx": r_vx, "vy": r_vy, 
                        "facing_right": r_facing, "max_hp": r_max_hp, 
                        "slam_active": r_slam, "dash_active": r_dash,
                        "invul_timer": r_invul,
                        "flash_on_invul": r_flash,
                        "action": r_action, "frame": r_frame
                    })
            except ValueError: continue

    def get_remote_state(self):
        with self.lock: return dict(self.remote_state)
    
    def get_remote_lobby_mode(self):
        with self.lock: return self.remote_lobby_mode
    
    def get_remote_char_selection(self):
        with self.lock: return self.remote_char_color, self.remote_char_ability
    
    def get_enemy_updates(self):
        with self.lock:
            updates = self.remote_enemy_updates[:]
            self.remote_enemy_updates.clear()
            return updates
    
    def get_boss_state(self):
        with self.lock: return dict(self.remote_boss_state)
    
    def check_lobby_exit(self):
        with self.lock:
            val = self.remote_lobby_exit
            self.remote_lobby_exit = False
            return val

    def check_remote_start(self):
        with self.lock:
            val = self.remote_start_triggered
            self.remote_start_triggered = False 
            return val

    def consume_remote_game_over(self):
        with self.lock:
            flag = self.remote_game_over
            text = self.remote_winner_text
            if flag:
                self.remote_game_over = False
                self.remote_winner_text = ""
        return flag, text
    
    def kick_client(self):
        if self.sock and self.connected:
            try: self.sock.sendall(b"K|KICK\n")
            except: pass
            time.sleep(0.1)
            self.reset_connection_only()
