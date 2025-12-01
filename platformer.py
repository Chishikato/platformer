import pygame
import random
import json
import os
import socket
import threading
import time
import math
import select

# =========================
# CONFIG / CONSTANTS
# =========================
GAME_TITLE = "Get slimed"

# Internal resolution increased to 640x480 to fit menu items + blank space
VIRTUAL_W, VIRTUAL_H = 640, 480 
START_FPS = 60

# COLORS (Synthwave/Retro Palette)
COL_BG = (20, 20, 35)
COL_GRID = (40, 40, 60)
COL_ACCENT_1 = (0, 234, 255)        # Cyan
COL_ACCENT_2 = (255, 0, 85)         # Hot Pink
COL_ACCENT_3 = (255, 215, 0)        # Gold
COL_TEXT = (240, 240, 255)
COL_UI_BG = (15, 15, 25)
COL_UI_BORDER = (60, 60, 90)
COL_SHADOW = (10, 10, 15)

# BASE PHYSICS
BASE_GRAVITY = 1400.0
BASE_JUMP_VEL = -550.0
BASE_PLAYER_SPEED = 220.0
WALL_SLIDE_SPEED = 50.0 
WALL_JUMP_X = 250.0         
WALL_JUMP_Y = -450.0        

# Horizontal Scroll Constants
SCROLL_OFFSET_X = 200.0       

BASE_SLAM_SPEED = 900.0                 
BASE_SLAM_COOLDOWN = 1.0                
SLAM_BASE_RADIUS = 40.0         
SLAM_RADIUS_PER_HEIGHT = 0.25   

TILE_SIZE = 20 
# Ground level for horizontal play
GROUND_LEVEL = VIRTUAL_H - 2 * TILE_SIZE

# Stage configurations (Distance in pixels)
STAGE_1_END = 4000
STAGE_2_END = 9000
# Stage 3 is Endless (anything > STAGE_2_END)

# Path helpers
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_asset_path(*paths):
    """Resolves path relative to the script directory"""
    return os.path.join(SCRIPT_DIR, *paths)

LEADERBOARD_FILE = get_asset_path("data", "save", "leaderboard.json")
SAVE_FILE = get_asset_path("data", "save", "save_data.json")
SETTINGS_FILE = get_asset_path("data", "save", "settings.json")

# Screen modes
MODE_WINDOW = 0
MODE_FULLSCREEN = 1
MODE_BORDERLESS = 2

# Game states
STATE_MAIN_MENU = "main_menu"
STATE_SETTINGS = "settings"
STATE_GAME = "game"
STATE_MULTIPLAYER_MENU = "mp_menu"
STATE_LEADERBOARD = "leaderboard"
STATE_SHOP = "shop"

# Multiplayer roles
ROLE_LOCAL_ONLY = "local"
ROLE_HOST = "host"
ROLE_CLIENT = "client"

MODE_SINGLE = "single"
MODE_COOP = "coop"
MODE_VERSUS = "versus"

# UDP Discovery
DISCOVERY_PORT = 50008
DISCOVERY_MSG = b"PLATFORMER_HOST_HERE"


# =========================
# HELPERS
# =========================

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def lerp(start, end, t):
    return start + t * (end - start)

def draw_text_shadow(surf, font, text, x, y, col=COL_TEXT, shadow_col=COL_SHADOW,
                      center=False, pulse=False, time_val=0):
    offset_y = 0

    if pulse:
        # Slight bobbing
        offset_y = math.sin(time_val * 4) * 3

        # Base cyan from your palette
        base_r, base_g, base_b = COL_ACCENT_1  # (0, 234, 255)

        # Pulse brightness between ~60% and 100%
        bright = 0.6 + 0.4 * math.sin(time_val * 5)
        if bright < 0.0:
            bright = 0.0

        r = int(base_r * bright)
        g = int(base_g * bright)
        b = int(base_b * bright)
        col = (r, g, b)

        # Darker cyan for the shadow
        shadow_col = (r // 4, g // 4, b // 4)

    # Base text surfaces
    shad = font.render(text, False, shadow_col)
    fore = font.render(text, False, col)

    final_y = y + offset_y

    if center:
        rect = fore.get_rect(center=(x, final_y))

        if pulse:
            # Cyan glow: soft copies around the text
            glow = font.render(text, False, col)
            glow.set_alpha(90)
            for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2)]:
                surf.blit(glow, (rect.x + dx, rect.y + dy))

        surf.blit(shad, (rect.x + 2, rect.y + 2))
        surf.blit(fore, rect)
        return rect
    else:
        base_x, base_y = x, final_y

        if pulse:
            # Cyan glow: soft copies around the text
            glow = font.render(text, False, col)
            glow.set_alpha(90)
            for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2)]:
                surf.blit(glow, (base_x + dx, base_y + dy))

        surf.blit(shad, (base_x + 2, base_y + 2))
        surf.blit(fore, (base_x, base_y))
        return pygame.Rect(base_x, base_y, fore.get_width(), fore.get_height())


def draw_panel(surf, rect, color=COL_UI_BG, border=COL_UI_BORDER):
    pygame.draw.rect(surf, COL_SHADOW, (rect.x + 4, rect.y + 4, rect.w, rect.h), border_radius=6)
    pygame.draw.rect(surf, color, rect, border_radius=6)
    pygame.draw.rect(surf, border, rect, 2, border_radius=6)

# --- DATA PERSISTENCE ---

def ensure_save_dir():
    save_dir = os.path.dirname(SAVE_FILE)
    if not os.path.exists(save_dir):
        try:
            os.makedirs(save_dir)
        except OSError as e:
            print(f"Error creating save directory: {e}")

def load_leaderboard():
    ensure_save_dir()
    if not os.path.exists(LEADERBOARD_FILE):
        return {"single": [], "coop": [], "versus": []}
    try:
        with open(LEADERBOARD_FILE, "r") as f:
            data = json.load(f)
        for key in ("single", "coop", "versus"):
            data.setdefault(key, [])
        return data
    except Exception:
        return {"single": [], "coop": [], "versus": []}

def save_leaderboard(lb):
    ensure_save_dir()
    try:
        with open(LEADERBOARD_FILE, "w") as f:
            json.dump(lb, f, indent=2)
    except Exception:
        pass

def add_score(lb, mode, name, score):
    entry = {"name": name, "score": int(score), "time": time.time()}
    lb[mode].append(entry)
    lb[mode] = sorted(lb[mode], key=lambda e: e["score"], reverse=True)[:10]
    save_leaderboard(lb)

def load_save_data():
    ensure_save_dir()
    data = {
        "credits": 0.0,
        "upgrades": {"speed": 0, "jump": 0, "hp": 0, "slam": 0}
    }
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f:
                saved = json.load(f)
                if "coins" in saved:
                    data["credits"] = float(saved["coins"])
                else:
                    data["credits"] = float(saved.get("credits", 0))
                 
                if "upgrades" in saved:
                    for k in data["upgrades"]:
                        data["upgrades"][k] = saved["upgrades"].get(k, 0)
        except Exception:
            pass
    return data

def save_save_data(data):
    ensure_save_dir()
    try:
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Failed to save data: {e}")

UPGRADE_INFO = {
    "speed": {"name": "Agility", "base_cost": 50, "cost_mult": 1.5, "max": 10, "desc": "+5% Move Speed"},
    "jump":  {"name": "Rocket Boots", "base_cost": 60, "cost_mult": 1.6, "max": 10, "desc": "+3% Jump Height"},
    "hp":    {"name": "Iron Heart", "base_cost": 200, "cost_mult": 2.0, "max": 5,  "desc": "+1 Max HP"},
    "slam":  {"name": "Graviton", "base_cost": 80, "cost_mult": 1.4, "max": 10, "desc": "-8% Slam Cooldown"}
}

def get_upgrade_cost(key, current_level):
    info = UPGRADE_INFO[key]
    if current_level >= info["max"]: return 999999
    return int(info["base_cost"] * (info["cost_mult"] ** current_level))

# =========================
# BACKGROUND & PARALLAX
# =========================

class ParallaxBackground:
    def __init__(self, folder_name, screen_w, screen_h):
        self.layers = []
        self.screen_w = screen_w
        self.screen_h = screen_h
        
        candidates = [
            get_asset_path("data", "gfx", folder_name),
            get_asset_path("data", folder_name),
            get_asset_path(folder_name),
            os.path.join("data", "gfx", folder_name),
            folder_name
        ]
        
        base_path = None
        for path in candidates:
            if os.path.isdir(path):
                base_path = path
                break
        
        if base_path is None:
            # Fallback default logic will handle missing assets
            base_path = get_asset_path("data", "gfx", folder_name)

        self.factors = [0.0, 0.1, 0.2, 0.4, 0.6] 
        
        for i in range(1, 6):
            filename = f"{i}.png"
            path = os.path.join(base_path, filename)
            
            loaded = False
            if os.path.exists(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    scale = screen_h / img.get_height()
                    new_w = int(img.get_width() * scale)
                    new_h = int(img.get_height() * scale)
                    img = pygame.transform.scale(img, (new_w, new_h))
                    self.layers.append(img)
                    loaded = True
                except Exception:
                    pass
            
            if not loaded:
                self.layers.append(self._make_placeholder(i))

    def _make_placeholder(self, index):
        if index == 1: color = (20, 20, 40)
        elif index == 2: color = (40, 30, 60)
        elif index == 3: color = (60, 40, 80)
        elif index == 4: color = (80, 50, 90)
        else: color = (100, 60, 100)
        
        s = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        pygame.draw.rect(s, color, (0, self.screen_h - index * 50, self.screen_w, index * 50))
        return s

    def draw(self, surf, scroll_x):
        for i, layer in enumerate(self.layers):
            factor = self.factors[i] if i < len(self.factors) else 0.5
            rel_x = -(scroll_x * factor) % layer.get_width()
            
            surf.blit(layer, (rel_x - layer.get_width(), 0))
            if rel_x < self.screen_w:
                surf.blit(layer, (rel_x, 0))
            if rel_x + layer.get_width() < self.screen_w: 
                surf.blit(layer, (rel_x + layer.get_width(), 0))

# =========================
# VISUAL EFFECTS
# =========================

class Particle:
    def __init__(self, x, y, color, vx, vy, life):
        self.x, self.y = x, y
        self.color = color
        self.vx, self.vy = vx, vy
        self.life = life
        self.max_life = life

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt

    def draw(self, surf, cam_x, cam_y):
        if self.life > 0:
            ratio = self.life / self.max_life
            sz = max(1, int(4 * ratio))
            pygame.draw.rect(surf, self.color, (self.x - cam_x, self.y - cam_y, sz, sz))

class FloatingText:
    def __init__(self, x, y, text, font, color=COL_ACCENT_3):
        self.x, self.y = x, y
        self.text = text
        self.font = font
        self.color = color
        self.life = 1.0
        self.vy = -40.0

    def update(self, dt):
        self.y += self.vy * dt
        self.life -= dt

    def draw(self, surf, cam_x, cam_y):
        if self.life > 0:
            scale = 1.0
            if self.life > 0.8: scale = (1.0 - self.life) * 5.0
            txt_s = self.font.render(self.text, False, self.color)
            alpha = min(255, int(255 * (self.life * 1.5))) 
            txt_s.set_alpha(alpha)
            if scale != 1.0:
                w = int(txt_s.get_width() * scale)
                h = int(txt_s.get_height() * scale)
                if w > 0 and h > 0:
                    txt_s = pygame.transform.scale(txt_s, (w, h))
            surf.blit(txt_s, (self.x - cam_x - txt_s.get_width()//2, self.y - cam_y))

class Credit:
    def __init__(self, x, y, value):
        self.x, self.y = x, y
        self.w, self.h = 14, 14
        self.value = value
        self.vx = random.uniform(-50, 50)
        self.vy = -250 
        self.life = 15.0
        self.bounce_factor = 0.6
        self.anim_timer = random.random() * 10

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def update(self, dt, level):
        self.life -= dt
        self.anim_timer += dt
        self.vy += BASE_GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        r = self.rect()
        tiles = level.get_collision_tiles(r)
        for t in tiles:
            if r.colliderect(t):
                if self.vy > 0:
                    self.y = t.top - self.h
                    self.vy = -self.vy * self.bounce_factor
                    self.vx *= 0.9
                    if abs(self.vy) < 50: self.vy = 0
                elif self.vy < 0:
                    self.y = t.bottom
                    self.vy = 0
                r.y = int(self.y)

    def draw(self, surf, cam_x, cam_y):
        cx = int(self.x - cam_x + self.w // 2)
        cy = int(self.y - cam_y + self.h // 2)
        color = COL_ACCENT_3 if self.value >= 1 else (192, 192, 192)
        spin_width = abs(math.cos(self.anim_timer * 4)) * 6
        if spin_width < 1: spin_width = 1
        rect = pygame.Rect(cx - spin_width, cy - 6, spin_width * 2, 12)
        pygame.draw.ellipse(surf, color, rect)
        pygame.draw.ellipse(surf, (255, 255, 220), rect, 2)

particles = []
floating_texts = [] 

def spawn_dust(x, y, count=5, color=(200, 200, 200)):
    for _ in range(count):
        vx = random.uniform(-60, 60)
        vy = random.uniform(-30, -80)
        life = random.uniform(0.2, 0.5)
        particles.append(Particle(x, y, color, vx, vy, life))

def spawn_slam_impact(x, y, power):
    count = int(10 + power * 0.1)
    for _ in range(count):
        angle = random.uniform(0, 3.14159) 
        speed = random.uniform(50, 200)
        vx = math.cos(angle) * speed
        vy = -math.sin(angle) * speed
        particles.append(Particle(x, y, COL_ACCENT_2, vx, vy, 0.6))

def spawn_credit_text(x, y, amount, font):
    txt = f"+{amount:.1f} CREDIT"
    col = COL_ACCENT_1 if amount >= 1 else (200, 200, 200)
    floating_texts.append(FloatingText(x, y, txt, font, col))

def draw_gradient_background(surf, stage):
    # Determine colors based on stage
    if stage == 1:
        # Night / Blue
        top_color = (10, 10, 30)
        bottom_color = (40, 20, 60)
    elif stage == 2:
        # Sunset / Purple-Orange
        top_color = (60, 30, 80)
        bottom_color = (180, 80, 60)
    else:
        # Endless / Red-Matrix
        top_color = (20, 0, 0)
        bottom_color = (60, 10, 20)

    h = surf.get_height()
    w = surf.get_width()
    steps = 20
    step_h = math.ceil(h / steps)
    for i in range(steps):
        t = i / steps
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        pygame.draw.rect(surf, (r, g, b), (0, i * step_h, w, step_h))

# =========================
# ASSET MANAGEMENT
# =========================
def load_sprite_sheet(path, cols, rows, row_index, scale=1.5):
    """
    Extracts frames from a specific row in a sprite sheet.
    """
    frames = []
    if not os.path.exists(path):
        # Fallback: create a placeholder frame
        size = 32 # Default size for a missing slime sprite
        print(f"Warning: Sprite sheet not found: {path}")
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        s.fill((255, 0, 255)) # Hot pink placeholder
        frames.append(s)
        return frames

    try:
        sheet = pygame.image.load(path).convert_alpha()
        sheet_w = sheet.get_width()
        sheet_h = sheet.get_height()
        
        # Calculate expected frame size based on grid
        frame_w = sheet_w // cols
        frame_h = sheet_h // rows
        
        # Ensure row index is valid
        if not (0 <= row_index < rows):
            print(f"Error: Invalid row_index {row_index} for sheet with {rows} rows.")
            return frames

        for c in range(cols):
            rect = pygame.Rect(c * frame_w, row_index * frame_h, frame_w, frame_h)
            frame = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
            frame.blit(sheet, (0, 0), rect)
            
            # Crop to visible pixels (get just the slime)
            bbox = frame.get_bounding_rect()
            if bbox.width > 0 and bbox.height > 0:
                cropped = pygame.Surface((bbox.width, bbox.height), pygame.SRCALPHA)
                cropped.blit(frame, (0, 0), bbox)
                frame = cropped
            
            # Scale up slightly (1.5x for visibility and retro feel)
            frame = pygame.transform.scale(frame, (int(frame.get_width() * scale), int(frame.get_height() * scale)))
            frames.append(frame)
            
    except Exception as e:
        print(f"Error loading sprite sheet {path}: {e}")
        
    return frames

def make_tile_surface():
    surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
    pygame.draw.rect(surf, (30, 30, 45), (0, 0, TILE_SIZE, TILE_SIZE))
    pygame.draw.rect(surf, COL_ACCENT_1, (0, 0, TILE_SIZE, 2)) # Neon Top
    pygame.draw.rect(surf, (50, 50, 70), (2, 2, TILE_SIZE-4, TILE_SIZE-4))
    return surf

def make_enemy_surface():
    s = TILE_SIZE * 2
    surf = pygame.Surface((s, s), pygame.SRCALPHA)
    return surf

def make_wall_surface(h):
    surf = pygame.Surface((8, h), pygame.SRCALPHA)
    return surf

# =========================
# SETTINGS & UI
# =========================

class Settings:
    def __init__(self):
        self.master_volume = 0.6
        self.music_volume = 0.5
        self.sfx_volume = 0.8
        self.target_fps = START_FPS
        self.screen_mode = MODE_WINDOW
        self.load() # Load settings on initialization

    def apply_audio(self):
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(self.music_volume * self.master_volume)
            
    def save(self):
        ensure_save_dir()
        data = {
            "master_volume": self.master_volume,
            "music_volume": self.music_volume,
            "sfx_volume": self.sfx_volume,
            "screen_mode": self.screen_mode
        }
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
            
    def load(self):
        ensure_save_dir()
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                    self.master_volume = data.get("master_volume", 0.6)
                    self.music_volume = data.get("music_volume", 0.5)
                    self.sfx_volume = data.get("sfx_volume", 0.8)
                    self.screen_mode = data.get("screen_mode", MODE_WINDOW)
            except Exception as e:
                print(f"Error loading settings: {e}")

class Button:
    def __init__(self, rect, text, font, callback, color=COL_UI_BG, accent=COL_ACCENT_1):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.callback = callback
        self.hover = False
        self.base_color = color
        self.accent_color = accent
        self.disabled = False
        self.click_anim = 0
        self.hover_timer = 0.0

    def handle_event(self, event):
        if self.disabled: return
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.click_anim = 2
                if self.callback: self.callback()
        elif event.type == pygame.MOUSEBUTTONUP:
            self.click_anim = 0

    def draw(self, surf, dt=0.0):
        if self.hover: self.hover_timer += dt
        else: self.hover_timer = 0.0
        draw_rect = self.rect.copy()
        draw_rect.y += self.click_anim
        if not self.disabled:
            pygame.draw.rect(surf, COL_SHADOW, (draw_rect.x + 3, draw_rect.y + 3, draw_rect.w, draw_rect.h), border_radius=4)
        bg = self.base_color
        border = self.accent_color if self.hover else COL_UI_BORDER
        text_col = COL_TEXT
        if self.disabled:
            bg = (30, 30, 40)
            border = (50, 50, 60)
            text_col = (100, 100, 100)
        elif self.hover:
            pulse = (math.sin(self.hover_timer * 10) + 1) * 0.5
            r = min(255, bg[0] + 40 + int(20 * pulse))
            g = min(255, bg[1] + 40 + int(20 * pulse))
            b = min(255, bg[2] + 40 + int(20 * pulse))
            bg = (r, g, b)
            br = min(255, self.accent_color[0] + int(50 * pulse))
            border = (br, self.accent_color[1], self.accent_color[2])
        pygame.draw.rect(surf, bg, draw_rect, border_radius=4)
        pygame.draw.rect(surf, border, draw_rect, 2, border_radius=4)
        txt = self.font.render(self.text, False, text_col)
        surf.blit(txt, txt.get_rect(center=draw_rect.center))

class Toggle:
    def __init__(self, rect, label, font, options, get_index, set_index):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.font = font
        self.options = options
        self.get_index = get_index
        self.set_index = set_index
        self.hover = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                idx = (self.get_index() + 1) % len(self.options)
                self.set_index(idx)

    def draw(self, surf):
        draw_panel(surf, self.rect, border=COL_ACCENT_1 if self.hover else COL_UI_BORDER)
        label_s = self.font.render(self.label, False, COL_TEXT)
        surf.blit(label_s, (self.rect.x + 10, self.rect.centery - label_s.get_height()//2))
        idx = self.get_index()
        opt_text = self.options[idx] if 0 <= idx < len(self.options) else "?"
        opt_s = self.font.render(opt_text, False, COL_ACCENT_3)
        surf.blit(opt_s, (self.rect.right - opt_s.get_width() - 10, self.rect.centery - opt_s.get_height()//2))

class Slider:
    def __init__(self, rect, label, font, get_value, set_value, min_v=0.0, max_v=1.0):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.font = font
        self.get_value = get_value
        self.set_value = set_value
        self.min_v, self.max_v = min_v, max_v
        self.dragging = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.dragging = True
                self._update_from_mouse(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._update_from_mouse(event.pos[0])

    def _update_from_mouse(self, mx):
        x0, x1 = self.rect.x + 10, self.rect.right - 10
        t = clamp((mx - x0) / (x1 - x0), 0.0, 1.0)
        self.set_value(self.min_v + t * (self.max_v - self.min_v))

    def draw(self, surf):
        draw_panel(surf, self.rect)
        label_s = self.font.render(self.label, False, COL_TEXT)
        surf.blit(label_s, (self.rect.x + 10, self.rect.y + 5))
        line_y = self.rect.bottom - 15
        x0, x1 = self.rect.x + 10, self.rect.right - 10
        pygame.draw.line(surf, (100, 100, 120), (x0, line_y), (x1, line_y), 4)
        v = clamp(self.get_value(), self.min_v, self.max_v)
        t = (v - self.min_v) / (self.max_v - self.min_v + 1e-6)
        knob_x = x0 + t * (x1 - x0)
        pygame.draw.circle(surf, COL_ACCENT_1, (int(knob_x), line_y), 8)
        val_str = f"{int(v)}" if self.max_v > 2 else f"{v:.2f}"
        val_s = self.font.render(val_str, False, COL_ACCENT_3)
        surf.blit(val_s, (self.rect.right - val_s.get_width() - 10, self.rect.y + 5))

class TextInput:
    def __init__(self, rect, font, initial_text="", placeholder="", on_enter=None):
        self.rect = pygame.Rect(rect)
        self.font = font
        self.text = initial_text
        self.placeholder = placeholder
        self.on_enter = on_enter
        self.active = False
        self.cursor_timer = 0.0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                self.active = False
                if self.on_enter: self.on_enter(self.text)
            elif event.key == pygame.K_BACKSPACE: self.text = self.text[:-1]
            elif event.key == pygame.K_v and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                self.paste_text()
            else:
                if len(self.text) < 32 and event.unicode.isprintable(): self.text += event.unicode

    def paste_text(self):
        try:
            if hasattr(pygame.scrap, "get_text"):
                decoded = pygame.scrap.get_text()
            else:
                decoded = pygame.scrap.get(pygame.SCRAP_TEXT).decode("utf-8").strip("\x00")
            if decoded and len(self.text) + len(decoded) < 32:
                self.text += decoded
        except: pass

    def update(self, dt):
        self.cursor_timer += dt

    def draw(self, surf):
        border = COL_ACCENT_1 if self.active else COL_UI_BORDER
        pygame.draw.rect(surf, (10, 10, 15), self.rect, border_radius=4)
        pygame.draw.rect(surf, border, self.rect, 2, border_radius=4)
        prev_clip = surf.get_clip()
        surf.set_clip(self.rect.inflate(-4, -4))
        
        display_text = self.text
        text_col = COL_TEXT
        if not self.text and self.placeholder and not self.active:
            display_text = self.placeholder
            text_col = (100, 100, 100)
            
        txt_s = self.font.render(display_text, False, text_col)
        surf.blit(txt_s, (self.rect.x + 6, self.rect.centery - txt_s.get_height()//2))
        
        if self.active and (int(self.cursor_timer * 2) % 2 == 0):
            text_w = self.font.size(self.text)[0] if self.text else 0
            cx = self.rect.x + 6 + text_w + 2
            if cx < self.rect.right - 4:
                pygame.draw.line(surf, COL_TEXT, (cx, self.rect.y + 4), (cx, self.rect.bottom - 4), 2)
        surf.set_clip(prev_clip)

# =========================
# NETWORKING & DISCOVERY
# =========================

class RoomScanner:
    def __init__(self):
        self.found_hosts = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try: self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except: pass
        self.sock.setblocking(False)
        try: self.sock.bind(("", DISCOVERY_PORT))
        except: pass
    
    def broadcast(self):
        try: self.sock.sendto(DISCOVERY_MSG, ("<broadcast>", DISCOVERY_PORT))
        except: pass

    def listen(self):
        try:
            while True:
                data, addr = self.sock.recvfrom(1024)
                if data == DISCOVERY_MSG:
                    if addr[0] not in self.found_hosts: self.found_hosts.append(addr[0])
        except BlockingIOError: pass
        except Exception: pass

class NetworkManager:
    def __init__(self):
        self.role = ROLE_LOCAL_ONLY
        self.sock = None
        self.connected = False
        self.lock = threading.Lock()
        self.remote_state = {"x": 0.0, "y": 0.0, "alive": True, "score": 0, "seed": 0, "hp": 3}
        self.remote_lobby_mode = None 
        self._recv_buffer = ""
        self.remote_game_over = False
        self.remote_winner_text = ""
        self.remote_start_triggered = False 
        self.scanner = RoomScanner()
        self.broadcasting = False
        self.hosting = False 
        self.server_socket = None

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
        self.remote_state = {"x": 0.0, "y": 0.0, "alive": True, "score": 0, "seed": 0, "hp": 3}
        self._recv_buffer = ""

    def start_broadcast_thread(self):
        self.broadcasting = True
        def broadcast_loop():
            while self.hosting:
                if self.broadcasting and not self.connected: self.scanner.broadcast()
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
                    # Only look for a connection if we don't have one
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
                                    self.remote_state = {"x": 0.0, "y": 0.0, "alive": True, "score": 0, "seed": 0, "hp": 3} 
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

    def send_local_state(self, px, py, alive, score, seed=0, hp=3):
        if not self.connected or not self.sock: return
        line = f"{px:.2f},{py:.2f},{int(alive)},{int(score)},{int(seed)},{int(hp)}\n"
        try: self.sock.sendall(line.encode("utf-8"))
        except: pass

    def send_game_over(self, text):
        if not self.connected or not self.sock: return
        line = f"G|{text}\n"
        try: self.sock.sendall(line.encode("utf-8"))
        except: pass

    def send_lobby_mode(self, mode):
        if not self.connected or not self.sock: return
        line = f"M|{mode}\n"
        try: self.sock.sendall(line.encode("utf-8"))
        except: pass

    def send_start_game(self):
        if not self.connected or not self.sock: return
        line = "S|START\n"
        try: self.sock.sendall(line.encode("utf-8"))
        except: pass

    def poll_remote_state(self):
        if not self.sock: return
        try:
            data = self.sock.recv(4096)
            if not data: raise ConnectionResetError()
            self._recv_buffer += data.decode("utf-8")
        except (BlockingIOError, socket.timeout): return
        except Exception:
            with self.lock:
                if self.role == ROLE_HOST:
                    self.reset_connection_only()
                else:
                    self.close()
            return

        while "\n" in self._recv_buffer:
            line, self._recv_buffer = self._recv_buffer.split("\n", 1)
            if not line: continue
            
            if line.startswith("K|"):
                with self.lock:
                    # Client received kick: Close immediately
                    self.close()
                continue
            # -------------------------------

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
            
            # (Rest of standard position parsing...)
            parts = line.split(",")
            if len(parts) < 4: continue
            try:
                rx, ry = float(parts[0]), float(parts[1])
                alive, score = bool(int(parts[2])), int(parts[3])
                r_seed = int(parts[4]) if len(parts) > 4 else 0
                r_hp = int(parts[5]) if len(parts) > 5 else 3
            except ValueError: continue
            with self.lock:
                self.remote_state.update({"x": rx, "y": ry, "alive": alive, "score": score, "seed": r_seed, "hp": r_hp})

    def get_remote_state(self):
        with self.lock: return dict(self.remote_state)
    
    def get_remote_lobby_mode(self):
        with self.lock: return self.remote_lobby_mode

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
        """Host sends a kick message then drops the connection."""
        if self.sock and self.connected:
            try:
                # Send kick packet so client knows why they were dropped
                self.sock.sendall(b"K|KICK\n")
            except: pass
            
            time.sleep(0.1)
            self.reset_connection_only()

# =========================
# GAME ENTITIES
# =========================

class Player:
    COYOTE_TIME = 0.12
    JUMP_BUFFER = 0.12
    AIR_CONTROL = 0.9

    def __init__(self, color, x, y, stats=None, sprite_dict=None):
        self.color = color
        # Default visual size for rectangle, overridden by sprites if present
        self.w, self.h = TILE_SIZE, TILE_SIZE * 2
        self.x, self.y = x, y
        self.last_safe_x, self.last_safe_y = x, y
        self.vx, self.vy = 0.0, 0.0
        self.on_ground = False
        self.alive = True
        self.is_dying = False
        self.death_timer = 0.0
        
        self.stats_speed_lvl = stats.get("speed", 0) if stats else 0
        self.stats_jump_lvl = stats.get("jump", 0) if stats else 0
        self.stats_hp_lvl = stats.get("hp", 0) if stats else 0
        self.stats_slam_lvl = stats.get("slam", 0) if stats else 0

        self.max_hp = 3 + self.stats_hp_lvl
        self.hp = self.max_hp
        self.invul_timer = 0.0
        self.flash_on_invul = False # NEW: Controls if we flicker or not
        self.knockback_timer = 0.0

        self.speed_val = BASE_PLAYER_SPEED * (1.0 + 0.05 * self.stats_speed_lvl)
        self.jump_val = BASE_JUMP_VEL * (1.0 + 0.03 * self.stats_jump_lvl)
        self.slam_cd_val = max(0.1, BASE_SLAM_COOLDOWN * (1.0 - 0.08 * self.stats_slam_lvl))

        self.on_wall = False
        self.wall_dir = 0
        self.facing_right = True
        self.coyote_timer = 0.0
        self.jump_buffer_timer = 0.0
        self.jump_was_pressed = False
        self.slam_active = False
        self.slam_cooldown = 0.0
        self.slam_start_y = 0.0
        self.pending_slam_impact = False
        self.slam_impact_power = 0.0
        self.trail = []
        
        # Animation
        self.anim_timer = 0.0
        self.squash_timer = 0.0 
        self.shockwave_timer = 0.0
        # How long to keep air anim after landing
        self.landing_timer = 0.0
        
        # Sprite Animation Handling
        self.sprites = sprite_dict if sprite_dict else {}
        self.current_action = "idle"
        self.frame_index = 0
        self.anim_speed = 0.1 # Default

        # Jump & fall frames (fall = subset of jump)
        self.jump_frames = self.sprites.get("jump", [])
        if self.jump_frames:
            # Use 0–4 as "takeoff" for jump anim
            self.jump_takeoff_max = min(4, len(self.jump_frames) - 1)
            # Fall uses only frames 5–10 (clamped to sheet length)
            self.fall_start_idx = min(5, len(self.jump_frames) - 1)
            self.fall_end_idx   = min(10, len(self.jump_frames) - 1)
        else:
            self.jump_takeoff_max = 0
            self.fall_start_idx = 0
            self.fall_end_idx = 0

        # Slam uses its own frames if present, otherwise jump frames
        self.slam_frames = self.sprites.get("slam_frames", self.jump_frames)

        # New Idle State Management
        self.idle_state = "main" # "main", "alt1", "alt2"
        self.idle_alt_trigger_count = random.randint(7, 12) # Triggers alt idle after this many main loops
        self.idle_main_loop_counter = 0
        
        # Update collider size based on first sprite if available
        if self.sprites and "idle_main" in self.sprites and self.sprites["idle_main"]:
            ref_surf = self.sprites["idle_main"][0]
            # Hitbox matches sprite size
            self.w = ref_surf.get_width()
            self.h = ref_surf.get_height()
        else:
            # Fallback sizes
            self.w = 20
            self.h = 20

    def rect(self):
        # Centered collider
        return pygame.Rect(int(self.x), int(self.y), int(self.w), int(self.h))

    # (Keep update method exactly the same as before, no changes needed there)
    def update(self, dt, level, input_left, input_right, input_jump, input_slam):
        if not self.alive: return

        # --- DEATH LOGIC ---
        if self.is_dying:
            input_left = input_right = input_jump = input_slam = False
            self.death_timer -= dt
            if self.death_timer <= 0:
                self.alive = False
                return
            self.current_action = "die"
            if self.on_ground: self.vx = 0

        # --- KNOCKBACK LOGIC (NEW) ---
        # If being knocked back, disable control inputs and tick down timer
        if self.knockback_timer > 0:
            self.knockback_timer -= dt
            input_left = False
            input_right = False
            input_jump = False
            input_slam = False
            # Apply a bit of drag to the knockback so they don't slide forever
            if self.on_ground:
                self.vx *= 0.9

        if self.on_ground and self.knockback_timer <= 0 and not self.is_dying:
            self.last_safe_x = self.x
            self.last_safe_y = self.y

        # Standard Timers
        self.anim_timer += dt
        if self.squash_timer > 0: self.squash_timer -= dt
        if self.shockwave_timer > 0: self.shockwave_timer -= dt
        if self.slam_active: self.trail.append([self.x, self.y, 200])
        if self.invul_timer > 0: self.invul_timer -= dt

        for t in self.trail:
            t[2] -= 1000 * dt
        self.trail = [t for t in self.trail if t[2] > 0]

        was_on_ground = self.on_ground
        self.pending_slam_impact = False
        if self.slam_cooldown > 0.0:
            self.slam_cooldown = max(0.0, self.slam_cooldown - dt)
        
        # Coyote time & Jump Buffer
        if self.on_ground: self.coyote_timer = self.COYOTE_TIME
        else: self.coyote_timer = max(0.0, self.coyote_timer - dt)

        if input_jump and not self.jump_was_pressed: self.jump_buffer_timer = self.JUMP_BUFFER
        else: self.jump_buffer_timer = max(0.0, self.jump_buffer_timer - dt)
        self.jump_was_pressed = input_jump

        # MOVEMENT PHYSICS
        desired_vx = 0.0
        if not self.is_dying and self.knockback_timer <= 0: # Only move if not dying AND not stunned
            if input_left: 
                desired_vx -= self.speed_val
                self.facing_right = False
            if input_right: 
                desired_vx += self.speed_val
                self.facing_right = True

        if self.on_ground: 
            if self.knockback_timer > 0:
                # Friction during knockback on ground
                self.vx = lerp(self.vx, 0, dt * 5)
            else:
                self.vx = 0 if self.is_dying else desired_vx
        else: 
            # Air control
            if self.knockback_timer > 0:
                # Less air control during knockback
                pass 
            else:
                self.vx += (desired_vx - self.vx) * self.AIR_CONTROL * dt * 10.0

        # Slam Logic
        can_slam = (not self.on_ground) and (not self.slam_active) and (self.slam_cooldown <= 0.0) and (not self.is_dying)
        if input_slam and can_slam and self.knockback_timer <= 0:
            self.slam_active = True
            self.slam_start_y = self.y
            self.vy = BASE_SLAM_SPEED
            spawn_dust(self.x + self.w/2, self.y, count=5, color=COL_ACCENT_1)

        # Gravity & Wall Logic
        self.vy += BASE_GRAVITY * dt
        if self.on_wall and not self.on_ground and self.vy > 0 and not self.slam_active and not self.is_dying and self.knockback_timer <= 0:
            if self.vy > WALL_SLIDE_SPEED:
                self.vy = WALL_SLIDE_SPEED
                if random.random() < 0.2:
                    offset_x = 0 if self.wall_dir == 1 else self.w
                    spawn_dust(self.x + offset_x, self.y + self.h, 1)

        # Variable jump height
        if (not input_jump) and (self.vy < 0) and (not self.slam_active) and self.knockback_timer <= 0:
            self.vy += BASE_GRAVITY * dt * 0.6

        # Jumps
        if (not self.slam_active) and self.jump_buffer_timer > 0.0 and self.coyote_timer > 0.0 and not self.is_dying and self.knockback_timer <= 0:
            self.vy = self.jump_val
            self.on_ground = False
            self.coyote_timer = 0.0
            self.jump_buffer_timer = 0.0
            spawn_dust(self.x + self.w/2, self.y + self.h, count=8)

        if (not self.slam_active) and self.jump_buffer_timer > 0.0 and self.on_wall and not self.on_ground and not self.is_dying and self.knockback_timer <= 0:
            self.vy = WALL_JUMP_Y
            self.vx = -self.wall_dir * WALL_JUMP_X 
            self.jump_buffer_timer = 0.0
            self.on_wall = False
            spawn_dust(self.x + (0 if self.wall_dir == 1 else self.w), self.y + self.h/2, count=6)

        # --- COLLISION LOGIC ---
        nx = self.x + self.vx * dt
        ny = self.y + self.vy * dt
        self.on_ground = False
        rect = pygame.Rect(int(nx), int(ny), int(self.w), int(self.h))
        tiles = level.get_collision_tiles(rect)
        self.y = ny
        rect.y = int(self.y)
        
        for t in tiles:
            if rect.colliderect(t):
                if self.vy > 0: 
                    self.y = t.top - self.h
                    self.vy = 0.0
                    self.on_ground = True
                elif self.vy < 0: 
                    self.y = t.bottom
                    self.vy = 0.0
                rect.y = int(self.y)

        self.x = nx
        rect.x = int(self.x)
        tiles = level.get_collision_tiles(rect)
        self.on_wall = False 
        for t in tiles:
            if rect.colliderect(t):
                if self.vx > 0:
                    self.x = t.left - self.w
                    if not self.on_ground:
                        self.on_wall = True
                        self.wall_dir = 1
                elif self.vx < 0:
                    self.x = t.right
                    if not self.on_ground:
                        self.on_wall = True
                        self.wall_dir = -1
                rect.x = int(self.x)

        # Extra floor check
        if not self.on_ground and self.vy >= 0:
            feet_check = pygame.Rect(int(self.x), int(self.y + self.h), int(self.w), 2)
            feet_tiles = level.get_collision_tiles(feet_check)
            for t in feet_tiles:
                if feet_check.colliderect(t):
                    self.y = t.top - self.h
                    self.vy = 0
                    self.on_ground = True
                    break
        
        # --- LANDING TIMER ---
        just_landed = self.on_ground and not was_on_ground
        if just_landed:
            # Short timer just to keep the "land" state active
            self.landing_timer = 0.1 
        elif self.landing_timer > 0.0:
            self.landing_timer = max(0.0, self.landing_timer - dt)

        # Slam impact at landing
        if self.slam_active and (not was_on_ground) and self.on_ground:
            self.slam_active = False
            self.slam_cooldown = self.slam_cd_val
            self.pending_slam_impact = True
            self.slam_impact_power = max(0.0, self.y - self.slam_start_y)
            spawn_slam_impact(self.x + self.w/2, self.y + self.h, self.slam_impact_power)
            self.shockwave_timer = 0.3
        
        # --- Animation State Logic ---
        prev_action = self.current_action
        new_action = prev_action
        
        if self.is_dying:
            new_action = "die" 
        elif self.slam_active: 
            new_action = "slam"
        # Only play hit animation if recently hit (knockback) or periodic invul
        elif self.knockback_timer > 0:
             new_action = "hit"
        else:
            # Force "land" state while timer is active
            if self.landing_timer > 0.0:
                 new_action = "land"
            elif not self.on_ground:
                if self.vy < 0: new_action = "jump"
                elif self.vy > 0: new_action = "fall"
            else:
                if abs(self.vx) > 1.0: new_action = "move"
                else: new_action = "idle"
        
        if new_action != prev_action:
            prev_frame = self.frame_index
            self.anim_timer = 0.0
            
            # --- TRANSITION LOGIC ---
            # If we fall -> land, simply SNAP to frame 9 (the one after the pause)
            if prev_action == "fall" and new_action == "land":
                self.frame_index = 9
            # If we jump -> fall, smooth handoff
            elif prev_action == "jump" and new_action == "fall" and self.jump_frames:
                world_idx = prev_frame
                world_idx = max(self.fall_start_idx, min(self.fall_end_idx, world_idx))
                self.frame_index = world_idx - self.fall_start_idx
            else:
                self.frame_index = 0

            self.current_action = new_action
            if new_action != "idle": self.idle_state = "main" 

        # =========================
        # PER-ACTION ANIMATION
        # =========================
        if not self.sprites: return

        # --- LAND ANIMATION ---
        # Just hold the frame we set in the transition logic (Frame 9)
        if self.current_action == "land":
            self.frame_index = 9
            return

        # --- Slam Animation ---
        if self.current_action == "slam":
            frames = self.slam_frames
            if frames:
                speed = 0.06
                if self.anim_timer > speed:
                    if self.frame_index < len(frames) - 1:
                        self.frame_index += 1
                    self.anim_timer = 0.0
            return 

        # --- Fall Animation ---
        if self.current_action == "fall" and self.jump_frames:
            # Pause at frame 8
            target_raw_frame = 8
            relative_stop_index = target_raw_frame - self.fall_start_idx
            fall_len = max(1, self.fall_end_idx - self.fall_start_idx + 1)
            actual_max = min(relative_stop_index, fall_len - 1)

            speed = 0.09
            if self.anim_timer > speed:
                if self.frame_index < actual_max:
                    self.frame_index += 1
                self.anim_timer = 0.0
            return

        # --- Idle Animation ---
        if self.current_action == "idle":
            frames = self.sprites.get(f"idle_{self.idle_state}", self.sprites.get("idle_main", []))
            anim_len = len(frames)
            if anim_len == 0: return
            speed = 0.2
            if self.anim_timer > speed:
                self.frame_index = (self.frame_index + 1) % anim_len
                self.anim_timer = 0.0
                if self.frame_index == 0 and self.idle_state == "main":
                    self.idle_main_loop_counter += 1
                    if self.idle_main_loop_counter >= self.idle_alt_trigger_count:
                        self.idle_state = random.choice(["alt1", "alt2"])
                        self.idle_main_loop_counter = 0
                        self.idle_alt_trigger_count = random.randint(7, 12)
                elif self.frame_index == 0 and self.idle_state in ["alt1", "alt2"]:
                    self.idle_state = "main"
            return

        # --- Move / Jump / Hit / Die ---
        if self.current_action in ["move", "jump", "hit", "die"]:
            if self.current_action == "jump" and self.jump_frames:
                frames = self.jump_frames
                speed = 0.09
                if self.anim_timer > speed:
                    if self.frame_index < self.jump_takeoff_max:
                        self.frame_index = min(self.jump_takeoff_max, self.frame_index + 1)
                    self.anim_timer = 0.0
            else:
                frames = self.sprites.get(self.current_action, [])
                anim_len = len(frames)
                if anim_len == 0: return
                speed = 0.1
                if self.current_action == "die": speed = 0.15
                if self.anim_timer > speed:
                    if self.current_action == "die" and self.frame_index >= anim_len - 1:
                        self.frame_index = anim_len - 1
                    else:
                        self.frame_index = (self.frame_index + 1) % anim_len
                    self.anim_timer = 0.0

    def take_damage(self, amount, source_x=None):
        # Prevent damage if already dead/dying or invincible
        if self.invul_timer > 0 or self.slam_active or self.is_dying or not self.alive:
            return
        
        self.hp -= amount
        
        # --- HIT EFFECTS ---
        self.invul_timer = 1.2 
        self.flash_on_invul = True # Real damage causes flashing
        self.knockback_timer = 0.3 
        self.current_action = "hit" 
        
        # --- KNOCKBACK PHYSICS ---
        self.vy = -350 
        self.on_ground = False
        
        # Horizontal push
        kb_force = 300.0
        if source_x is not None:
            direction = -1 if (self.x + self.w/2) < source_x else 1
            self.vx = direction * kb_force
        else:
            self.vx = -kb_force if self.facing_right else kb_force

        if self.hp <= 0:
            self.hp = 0
            self.is_dying = True
            self.death_timer = 2.0 
            
            self.vy = -300 
            self.vx = 0 
            self.slam_active = False

    def draw(self, surf, cam_x, cam_y):
        # Ghost Trail
        for t in self.trail:
            rect = pygame.Rect(t[0] - cam_x, t[1] - cam_y, self.w, self.h)
            s = pygame.Surface((int(self.w), int(self.h)), pygame.SRCALPHA)
            s.fill(self.color)
            s.set_alpha(int(t[2] * 0.5))
            surf.blit(s, rect)

        # --- Perfectly Synced Hit Flicker ---
        # Only flicker if invul_timer > 0 AND flash_on_invul is True
        if self.invul_timer > 0 and self.flash_on_invul:
            if int(self.invul_timer * 15) % 2 != 0:
                return # Skip drawing this frame

        # Drawing based on sprites if available
        if self.sprites:
            # Determine which frames to use based on current action and idle state
            if self.current_action == "idle":
                frames = self.sprites.get(f"idle_{self.idle_state}", self.sprites.get("idle_main", []))
            elif self.current_action == "fall":
                if self.jump_frames:
                    frames = self.jump_frames[self.fall_start_idx:self.fall_end_idx + 1]
                else:
                    frames = self.sprites.get("jump", self.sprites.get("idle_main", []))
            elif self.current_action == "slam":
                frames = self.slam_frames or self.jump_frames or self.sprites.get("idle_main", [])
            else:
                frames = self.sprites.get(self.current_action, self.sprites.get("idle_main", []))

            if not frames: 
                draw_x = self.x - cam_x
                draw_y = self.y - cam_y
                pygame.draw.rect(surf, self.color, (draw_x, draw_y, self.w, self.h))
                return
                
            idx = self.frame_index % len(frames)
            img = frames[idx]
            
            if not self.facing_right:
                img = pygame.transform.flip(img, True, False)
            
            # Center sprite on the physics box
            phys_center_x = self.x + self.w / 2
            phys_bottom = self.y + self.h
            
            sprite_draw_x = phys_center_x - img.get_width() / 2 - cam_x
            sprite_draw_y = phys_bottom - img.get_height() - cam_y
            
            surf.blit(img, (sprite_draw_x, sprite_draw_y))
        else:
            # Fallback Drawing (Rectangle)
            draw_x = self.x - cam_x
            draw_y = self.y - cam_y
            pygame.draw.rect(surf, self.color, (draw_x, draw_y, self.w, self.h))

        if self.slam_active:
            # Draw speed lines
            cx = (self.x - cam_x) + self.w / 2
            top_y = (self.y - cam_y)
            pygame.draw.line(surf, (255, 255, 255), (cx, top_y), (cx, top_y - 40), 2)
            pygame.draw.line(surf, (255, 255, 255), (cx - 10, top_y + 10), (cx - 10, top_y - 20), 1)
            pygame.draw.line(surf, (255, 255, 255), (cx + 10, top_y + 10), (cx + 10, top_y - 20), 1)

        # Draw Shockwave
        if self.shockwave_timer > 0:
            max_rad = 100
            progress = 1.0 - (self.shockwave_timer / 0.3)
            rad = int(max_rad * progress)
            
            cx = int((self.x - cam_x) + self.w / 2)
            cy = int((self.y - cam_y) + self.h) 
            
            pygame.draw.circle(surf, (200, 255, 255), (cx, cy), rad, 2)

class Enemy:
    def __init__(self, sprite_dict, x, y, hp=1.0, is_boss=False):
        self.sprites = sprite_dict
        
        # Determine hitbox size based on the first frame of the walk animation
        if self.sprites and "walk" in self.sprites and len(self.sprites["walk"]) > 0:
            ref_surf = self.sprites["walk"][0]
            self.w, self.h = ref_surf.get_width(), ref_surf.get_height()
        else:
            self.w, self.h = 32, 32  # Fallback size if sprites fail to load

        self.x, self.y = x, y
        self.vx = 60.0  # Constant patrol speed
        self.vy = 0.0
        self.facing_right = True # Track direction for flipping sprites
        
        self.is_boss = is_boss 
        self.max_hp = hp
        self.hp = self.max_hp
        self.invul_timer = 0.0 
        
        self.alive = True
        self.anim_timer = 0.0
        self.frame_index = 0
        self.current_action = "walk"

    def rect(self): return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def take_damage(self, amount):
        if self.invul_timer > 0: return False
        
        self.hp -= amount
        self.invul_timer = 0.2 # Short invulnerability
        self.current_action = "hurt" # Switch to hurt animation
        self.frame_index = 0 # Reset frame for the hit reaction
        
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            return True
        return False

    def update(self, dt, players, level, cam_rect):
        if not self.alive: return False
        
        # --- ANIMATION TIMING ---
        self.anim_timer += dt
        anim_speed = 0.15
        if self.anim_timer > anim_speed:
            self.frame_index += 1
            self.anim_timer = 0.0

        # Reset state to walk if invul/hurt animation finishes
        if self.invul_timer <= 0:
            self.current_action = "walk"
        else:
            self.invul_timer -= dt

        # Direction check
        if self.vx > 0: self.facing_right = True
        elif self.vx < 0: self.facing_right = False
        
        # --- CLEANUP ---
        my_rect = self.rect()
        if not my_rect.colliderect(cam_rect):
            # Clean up if fell off screen or way behind
            if self.y > cam_rect.bottom + 500: self.alive = False
            if self.x < cam_rect.left - 200: self.alive = False
            return False

        # --- PHYSICS ---
        self.vy += BASE_GRAVITY * dt
        
        # Ledge Detection
        look_ahead_x = self.x + self.w + 5 if self.vx > 0 else self.x - 5
        feet_check = pygame.Rect(int(look_ahead_x), int(self.y + self.h + 2), 4, 4)
        if not level.get_collision_tiles(feet_check):
            self.vx *= -1

        ny = self.y + self.vy * dt
        rect = pygame.Rect(int(self.x), int(ny), self.w, self.h)
        tiles = level.get_collision_tiles(rect)
        self.y = ny
        rect.y = int(self.y)

        for t in tiles:
            if rect.colliderect(t) and self.vy > 0:
                self.y = t.top - self.h
                self.vy = 0.0
                rect.y = int(self.y)

        nx = self.x + self.vx * dt
        rect.x = int(nx)
        tiles = level.get_collision_tiles(rect)
        self.x = nx
        rect.x = int(self.x)
        
        # Wall Bounce
        for t in tiles:
            if rect.colliderect(t):
                if self.vx > 0: self.x = t.left - self.w
                elif self.vx < 0: self.x = t.right
                rect.x = int(self.x)
                self.vx *= -1 

        # --- SPIKE DAMAGE LOGIC ---
        # Check against level obstacles (spikes)
        my_hitbox = self.rect()
        for obs in level.obstacles:
            if my_hitbox.colliderect(obs):
                # Enemy hit a spike -> Insta-kill or high damage
                died = self.take_damage(10.0) 
                if died: return True 

        return False 

    def draw(self, surf, cam_x, cam_y):
        if not self.alive: return
        
        # Retrieve frames
        frames = self.sprites.get(self.current_action, self.sprites.get("walk", []))
        if not frames: return

        # Loop animation
        img = frames[self.frame_index % len(frames)]

        # Flip if moving right
        if self.facing_right:
            img = pygame.transform.flip(img, True, False)

        draw_x = self.x - cam_x
        draw_y = self.y - cam_y

        # Visual Flash effect when hurt
        if self.current_action == "hurt":
            if int(self.invul_timer * 20) % 2 == 0:
                # Create a white silhouette for flashing
                flash_surf = img.copy()
                flash_surf.fill((255, 255, 255, 200), special_flags=pygame.BLEND_RGBA_MULT)
                surf.blit(flash_surf, (draw_x, draw_y))
                return

        surf.blit(img, (draw_x, draw_y))
        
        # HP Bar (Mini) - Only show if damaged
        if self.hp < self.max_hp:
            bar_w = self.w
            bar_h = 3
            hp_pct = self.hp / self.max_hp
            pygame.draw.rect(surf, (0,0,0), (draw_x, draw_y - 6, bar_w, bar_h))
            pygame.draw.rect(surf, (255, 0, 0), (draw_x, draw_y - 6, bar_w * hp_pct, bar_h))

class LevelManager:
    def __init__(self, tile_surface, enemy_sprite_dict, seed):
        self.rng = random.Random(seed)
        self.tile_surf = tile_surface
        self.enemy_sprites = enemy_sprite_dict
        self.platform_segments = []
        self.enemies = []
        self.obstacles = []
        self.orbs = []
        self.dropped_credits = []
        
        # Start Generation at X=0
        self.generated_right_x = 0
        self.current_stage = 1
        
        # Track the Y level of the last generated platform to ensure continuity
        self.last_platform_y = GROUND_LEVEL 

        # Create initial safety platform
        self._add_segment(0, 800, self.last_platform_y)
        self.generated_right_x = 800
        
        self.gen_count = 0
        self.enemy_timer = 0
        self.orb_timer = 0.0

    def _add_segment(self, x_start, width, y):
        self.platform_segments.append(pygame.Rect(int(x_start), int(y), int(width), TILE_SIZE))

    def get_collision_tiles(self, rect):
        res = []
        for s in self.platform_segments:
            # Simple broad-phase check for performance
            if s.right < rect.left - 4 or s.left > rect.right + 4: continue
            if s.bottom < rect.top - 4 or s.top > rect.bottom + 4: continue
            res.append(s)
        return res

    def _generate_section(self):
        # Determine Stage based on distance
        if self.generated_right_x < STAGE_1_END:
            self.current_stage = 1
        elif self.generated_right_x < STAGE_2_END:
            self.current_stage = 2
        else:
            self.current_stage = 3 # Endless

        # Determine Height Change (Delta Y)
        # Note: Negative Delta Y means going UP (screen coordinates)
        # Max Jump Height with current physics is approx 108 pixels.
        # We limit upward generation to 4 tiles (80px) to be safe.
        
        min_change = 0
        max_change = 0

        if self.current_stage == 1:
            # Mostly flat, slight bumps
            min_change = -2 # Up 2 tiles
            max_change = 2  # Down 2 tiles
        elif self.current_stage == 2:
            # Verticality intro
            min_change = -4 # Up 4 tiles (Hard jump)
            max_change = 5  # Down 5 tiles
        else:
            # Endless chaos
            min_change = -4
            max_change = 8  # Big drops

        delta_tiles = self.rng.randint(min_change, max_change)
        new_y = self.last_platform_y + (delta_tiles * TILE_SIZE)

        # Clamp Y to keep play area reasonable
        # Don't go too high (0) or fall into the void (VIRTUAL_H)
        min_allowed_y = TILE_SIZE * 4
        max_allowed_y = VIRTUAL_H - TILE_SIZE * 2
        
        if new_y < min_allowed_y: 
            new_y = min_allowed_y + TILE_SIZE # Bounce down
        elif new_y > max_allowed_y: 
            new_y = max_allowed_y - TILE_SIZE # Bounce up

        # Determine Gap Width based on Height Change
        # If we are going UP (new_y < last_y), the gap must be smaller
        # If we are going DOWN (new_y > last_y), the gap can be larger
        
        base_gap = 60
        gap_variance = self.rng.randint(0, 40)
        
        height_diff = self.last_platform_y - new_y # Positive = Going UP
        
        if height_diff > 0:
            # We are jumping UP. Reduce gap significantly.
            # For every tile up (20px), reduce gap capacity
            penalty = (height_diff / TILE_SIZE) * 12
            final_gap = max(40, (base_gap + gap_variance) - penalty)
        else:
            # We are jumping DOWN or FLAT. Increase gap.
            bonus = (abs(height_diff) / TILE_SIZE) * 8
            final_gap = base_gap + gap_variance + bonus
            # Cap max gap to avoid impossible horizontal leaps (Max flat jump is ~170px)
            final_gap = min(final_gap, 150)

        final_gap = int(final_gap)
        
        # Calculate X position
        new_x = self.generated_right_x + final_gap

        plat_w = TILE_SIZE * self.rng.randint(4, 12)
        
        # Add the segment
        self._add_segment(new_x, plat_w, new_y)
        
        # Update trackers
        self.generated_right_x = new_x + plat_w
        self.last_platform_y = new_y # IMPORTANT: Save for next loop
        self.gen_count += 1

        
        # Enemy Spawn Chance
        enemy_chance = 0.3
        if self.current_stage == 2: enemy_chance = 0.5
        if self.current_stage == 3: enemy_chance = 0.7
        
        ref_width = 32
        ref_height = 32
        if "walk" in self.enemy_sprites and self.enemy_sprites["walk"]:
            ref_surf = self.enemy_sprites["walk"][0]
            ref_width = ref_surf.get_width()
            ref_height = ref_surf.get_height()

        # Only spawn enemies on platforms wide enough
        if self.rng.random() < enemy_chance and plat_w > TILE_SIZE * 6:
            ex = new_x + plat_w // 2 - ref_width // 2
            ey = new_y - ref_height
            self.enemies.append(Enemy(self.enemy_sprites, ex, ey))
        
        if self.rng.random() < 0.25 and self.current_stage > 1 and plat_w > TILE_SIZE * 6:
            spike_x = new_x + self.rng.randint(3, (plat_w // TILE_SIZE) - 3) * TILE_SIZE
            self.obstacles.append(pygame.Rect(spike_x, new_y - TILE_SIZE, TILE_SIZE, TILE_SIZE))

        # Orb Chance
        if self.rng.random() < 0.5:
             orb_size = TILE_SIZE // 2
             ox = new_x + plat_w // 2 - orb_size // 2
             self.orbs.append(pygame.Rect(ox, new_y - 3 * TILE_SIZE, orb_size, orb_size))

    def spawn_credit(self, x, y, value):
        self.dropped_credits.append(Credit(x, y, value))

    def update(self, dt, cam_x, difficulty):
        self.orb_timer += dt
        
        # Generate ahead of camera (Right side)
        target_right = cam_x + VIRTUAL_W + 400
        while self.generated_right_x < target_right:
            self._generate_section()
            
        # Cleanup behind camera (Left side)
        cleanup_x = cam_x - 200
        
        self.platform_segments = [s for s in self.platform_segments if s.right > cleanup_x]
        self.obstacles = [o for o in self.obstacles if o.right > cleanup_x]
        self.orbs = [o for o in self.orbs if o.right > cleanup_x]
        self.enemies = [e for e in self.enemies if e.alive and e.x > cleanup_x]
        
        for c in self.dropped_credits: c.update(dt, self)
        self.dropped_credits = [c for c in self.dropped_credits if c.life > 0 and c.x > cleanup_x]

    def update_enemies(self, dt, players, cam_rect):
        spike_deaths = []
        for e in self.enemies:
            if e.update(dt, players, self, cam_rect): spike_deaths.append((e.x, e.y))
        self.enemies = [e for e in self.enemies if e.alive]
        return spike_deaths

    def draw(self, surf, cam_x, cam_y):
        for s in self.platform_segments:
            if s.right - cam_x < 0 or s.left - cam_x > VIRTUAL_W: continue
            
            for x in range(s.left, s.right, TILE_SIZE):
                surf.blit(self.tile_surf, (x - cam_x, s.top - cam_y))

        for o in self.obstacles:
            bx = o.x - cam_x
            by = o.y + o.h - cam_y
            points = [(bx, by), (bx + o.w, by), (bx + o.w / 2, by - o.h)]
            pygame.draw.polygon(surf, (200, 50, 50), points)
            pygame.draw.polygon(surf, (100, 0, 0), points, 2)
        
        # Orb Bobbing
        bob = math.sin(self.orb_timer * 3) * 3
        
        for orb in self.orbs:
            cx = orb.x - cam_x + orb.w // 2
            cy = orb.y - cam_y + orb.h // 2 + bob
            pygame.draw.circle(surf, COL_ACCENT_3, (cx, cy), orb.w // 2)
            pygame.draw.circle(surf, (255, 255, 200), (cx, cy), orb.w // 2 + 2, 1)
        for c in self.dropped_credits: c.draw(surf, cam_x, cam_y)
        for e in self.enemies: e.draw(surf, cam_x, cam_y)

# =========================
# MAIN GAME LOOP
# =========================
def main():
    pygame.init()
    pygame.mixer.init()

    settings = Settings()
    settings.apply_audio()
    
    # DEFAULT TO 720p WINDOW (Double the internal resolution)
    window = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
    pygame.display.set_caption(GAME_TITLE)
    apply_screen_mode(window, settings.screen_mode)
    
    clock = pygame.time.Clock()
    canvas = pygame.Surface((VIRTUAL_W, VIRTUAL_H))
    
    # Use standard system fonts but drawn carefully
    font_small = pygame.font.SysFont("arial", 12, bold=True)
    font_med = pygame.font.SysFont("arial", 18, bold=True)
    font_big = pygame.font.SysFont("arial", 32, bold=True)

    # === SPRITE LOADING ===
    # Load sprites from data/gfx/Slimes/
    slime_path = get_asset_path("data", "gfx", "Slimes")
    
    # --- P1 (Blue - Row index 3) ---
    p1_idle_main = load_sprite_sheet(os.path.join(slime_path, "slime_idle1.png"), 2, 7, 3)
    p1_idle_alt1 = load_sprite_sheet(os.path.join(slime_path, "slime_idle2.png"), 7, 7, 3)
    p1_idle_alt2 = load_sprite_sheet(os.path.join(slime_path, "slime_idle3.png"), 7, 7, 3)
    p1_jump_frames = load_sprite_sheet(os.path.join(slime_path, "slime_jump.png"), 11, 7, 3) # Corrected cols to 11

    p1_sprites = {
        # Idle states for random switching
        "idle_main": p1_idle_main,
        "idle_alt1": p1_idle_alt1,
        "idle_alt2": p1_idle_alt2,
        
        "move": load_sprite_sheet(os.path.join(slime_path, "slime_move.png"), 7, 7, 3),
        "jump": p1_jump_frames,
        "fall": p1_jump_frames, # Fall uses the same frames as jump
        "slam_frames": p1_jump_frames, # Slam uses the jump frames for dive, reversed in update logic
        "hit": load_sprite_sheet(os.path.join(slime_path, "slime_hit.png"), 2, 7, 3), # Corrected cols to 2
        "die": load_sprite_sheet(os.path.join(slime_path, "slime_die.png"), 13, 7, 3), # Corrected cols to 13
        "swallow": load_sprite_sheet(os.path.join(slime_path, "slime_swallow.png"), 14, 7, 3) # Corrected cols to 14 (Unused, but loaded)
    }

    # --- P2 (Red - Row index 1) - For contrast ---
    p2_idle_main = load_sprite_sheet(os.path.join(slime_path, "slime_idle1.png"), 2, 7, 1)
    p2_idle_alt1 = load_sprite_sheet(os.path.join(slime_path, "slime_idle2.png"), 7, 7, 1)
    p2_idle_alt2 = load_sprite_sheet(os.path.join(slime_path, "slime_idle3.png"), 7, 7, 1)
    p2_jump_frames = load_sprite_sheet(os.path.join(slime_path, "slime_jump.png"), 11, 7, 1) # Corrected cols to 11

    p2_sprites = {
        # Idle states for random switching
        "idle_main": p2_idle_main,
        "idle_alt1": p2_idle_alt1,
        "idle_alt2": p2_idle_alt2,
        
        "move": load_sprite_sheet(os.path.join(slime_path, "slime_move.png"), 7, 7, 1),
        "jump": p2_jump_frames,
        "fall": p2_jump_frames, # Fall uses the same frames as jump
        "slam_frames": p2_jump_frames, # Slam uses the jump frames for dive, reversed in update logic
        "hit": load_sprite_sheet(os.path.join(slime_path, "slime_hit.png"), 2, 7, 1), # Corrected cols to 2
        "die": load_sprite_sheet(os.path.join(slime_path, "slime_die.png"), 13, 7, 1), # Corrected cols to 13
        "swallow": load_sprite_sheet(os.path.join(slime_path, "slime_swallow.png"), 14, 7, 1) # Corrected cols to 14 (Unused, but loaded)
    }

    player1_sprite = p1_sprites
    player2_sprite = p2_sprites
    
    # --- ENEMY SPRITES (UPDATED PATH) ---
    # Path is: data/gfx/Enemy
    enemy_path = get_asset_path("data", "gfx", "Enemy")

    ENEMY_SCALE = 0.9
    
    # Load spritesheets (4 columns, 1 row)
    enemy_walk_frames = load_sprite_sheet(os.path.join(enemy_path, "spr_monster_reg_strip4.png"), 4, 1, 0, scale=ENEMY_SCALE)
    enemy_hurt_frames = load_sprite_sheet(os.path.join(enemy_path, "spr_enemy_reg_hurt_strip4.png"), 4, 1, 0, scale=ENEMY_SCALE)

    # Pack into dictionary
    enemy_sprite_dict = {
        "walk": enemy_walk_frames,
        "hurt": enemy_hurt_frames
    }

    tile_surf = make_tile_surface()
    wall_surf = make_wall_surface(VIRTUAL_H)

    running = True
    game_state = STATE_MAIN_MENU
    lb = load_leaderboard()
    save_data = load_save_data()
    network = NetworkManager()
    
    # Load Backgrounds
    day_bg = ParallaxBackground("Day", VIRTUAL_W, VIRTUAL_H)
    night_bg = ParallaxBackground("Night", VIRTUAL_W, VIRTUAL_H)
    menu_scroll_x = 0.0

    # Load Menu Music
    MENU_BGM_PATH = get_asset_path("data", "sfx", "ui_bgm_space_riddle.flac")
    menu_music_loaded = False
    if os.path.exists(MENU_BGM_PATH):
        try:
            pygame.mixer.music.load(MENU_BGM_PATH)
            menu_music_loaded = True
            pygame.mixer.music.play(-1)
        except Exception as e:
            print(f"Music load failed: {e}")
    
    main_buttons = []
    settings_widgets = []
    shop_buttons = []
    settings_scroll = 0.0
    mp_buttons = []
    mp_mode = MODE_VERSUS
    show_kick_confirm = False
    
    # Initialize with placeholder text
    mp_ip_input = TextInput(pygame.Rect(140, 170, 200, 30), font_small, "", "Enter IP Address...")
    
    room_list = []
    selected_room = None
    
    global_anim_timer = 0.0

    def rebuild_main_menu():
        main_buttons.clear()
        y = 120
        def add_btn(label, cb, color=COL_UI_BG, accent=COL_ACCENT_1):
            nonlocal y
            rect = pygame.Rect(VIRTUAL_W // 2 - 100, y, 200, 40)
            main_buttons.append(Button(rect, label, font_med, cb, color=color, accent=accent))
            y += 50
        
        add_btn("Single Player", lambda: start_game(settings, window, canvas, font_small, font_med, font_big, player1_sprite, player2_sprite, enemy_sprite_dict, tile_surf, wall_surf, lb, network, ROLE_LOCAL_ONLY, MODE_SINGLE, None, local_two_players=False, bg_obj=night_bg))
        add_btn("Multiplayer", lambda: set_state(STATE_MULTIPLAYER_MENU), accent=COL_ACCENT_3)
        add_btn("Shop", lambda: set_state(STATE_SHOP))
        add_btn("Settings", lambda: set_state(STATE_SETTINGS))
        add_btn("Quit", lambda: stop(), color=(40, 10, 10))

    def rebuild_shop_menu():
        shop_buttons.clear()
        shop_buttons.append(Button(pygame.Rect(20, VIRTUAL_H - 50, 80, 30), "Back", font_small, lambda: set_state(STATE_MAIN_MENU)))
        
        y_start = 70
        row_height = 65  # Increased spacing to create gaps
        panel_h = 50
        btn_h = 35
        # Calculate vertical center offset for the button relative to the panel
        btn_y_off = (panel_h - btn_h) // 2

        for i, (key, info) in enumerate(UPGRADE_INFO.items()):
            lvl = save_data["upgrades"].get(key, 0)
            cost = get_upgrade_cost(key, lvl)
            is_max = lvl >= info["max"]
            row_y = y_start + i * row_height
            
            def buy_action(k=key):
                nonlocal save_data
                l = save_data["upgrades"].get(k, 0)
                c = get_upgrade_cost(k, l)
                if save_data["credits"] >= c and l < UPGRADE_INFO[k]["max"]:
                    save_data["credits"] -= c
                    save_data["upgrades"][k] = l + 1
                    save_save_data(save_data)
                    rebuild_shop_menu()
            
            btn_text = "MAXED" if is_max else f"Buy ({cost})"
            # Button is now vertically centered in the panel
            btn = Button(pygame.Rect(VIRTUAL_W - 140, row_y + btn_y_off, 90, btn_h), btn_text, font_small, buy_action, accent=COL_ACCENT_3)
            if save_data["credits"] < cost or is_max: btn.disabled = True
            shop_buttons.append(btn)

    def rebuild_settings_menu():
        nonlocal settings_scroll
        settings_widgets.clear()
        settings_scroll = 0.0
        y = 80
        widget_height = 40
        widget_spacing = 15
        
        def add_slider(label, get_v, set_v, min_v=0.0, max_v=1.0):
            nonlocal y
            r = pygame.Rect(100, y, VIRTUAL_W - 200, widget_height)
            settings_widgets.append(Slider(r, label, font_small, get_v, set_v, min_v, max_v))
            y += widget_height + widget_spacing
        
        def add_toggle(label, options, get_idx, set_idx):
            nonlocal y
            r = pygame.Rect(100, y, VIRTUAL_W - 200, widget_height)
            settings_widgets.append(Toggle(r, label, font_small, options, get_idx, set_idx))
            y += widget_height + widget_spacing

        # UPDATED: Removed settings.save() from callbacks to prevent disk I/O lag while dragging
        # Added settings.apply_audio() so you can hear volume changes in real-time
        add_slider("Master Volume", lambda: settings.master_volume, lambda v: (setattr(settings, "master_volume", v), settings.apply_audio()), 0.0, 1.0)
        add_slider("Music Volume", lambda: settings.music_volume, lambda v: (setattr(settings, "music_volume", v), settings.apply_audio()), 0.0, 1.0)
        add_slider("SFX Volume", lambda: settings.sfx_volume, lambda v: setattr(settings, "sfx_volume", v), 0.0, 1.0)
        add_toggle("Screen Mode", ["Window", "Fullscreen", "Borderless"], lambda: settings.screen_mode, lambda idx: (setattr(settings, "screen_mode", idx), apply_screen_mode(window, idx)))

    def rebuild_mp_menu():
        mp_buttons.clear()
        
        # ==============================
        # HOST LOBBY VIEW
        # ==============================
        if network.role == ROLE_HOST:
            # --- LEFT PANEL ---
            mp_buttons.append(Button(pygame.Rect(30, 70, 160, 40), "Room: HOST", font_med, None, color=COL_ACCENT_1))
            mp_buttons.append(Button(pygame.Rect(30, 120, 160, 30), "Invite Players", font_small, lambda: print("Invite clicked")))
            mp_buttons.append(Button(pygame.Rect(30, 160, 160, 30), "Kick Player", font_small, lambda: print("Kick clicked"), color=(60, 20, 20)))
            mp_buttons.append(Button(pygame.Rect(30, 270, 160, 30), "Disband Lobby", font_small, lambda: (network.close(), rebuild_mp_menu()), color=(80, 10, 10)))

            def trigger_kick_confirm():
                nonlocal show_kick_confirm
                show_kick_confirm = True

            kick_btn = Button(pygame.Rect(30, 160, 160, 30), "Kick Player", font_small, trigger_kick_confirm, color=(60, 20, 20))
            
            # Only enable kick button if someone is actually connected
            if not network.connected:
                kick_btn.disabled = True
                kick_btn.base_color = (40, 20, 20) # Dimmed
            
            mp_buttons.append(kick_btn)

            # --- RIGHT PANEL (Controls) ---
            def toggle_mode():
                nonlocal mp_mode
                mp_mode = MODE_COOP if mp_mode == MODE_VERSUS else MODE_VERSUS
                if network.role == ROLE_HOST: network.send_lobby_mode(mp_mode)
                rebuild_mp_menu()
            
            mode_txt = f"Mode: {'Co-op' if mp_mode == MODE_COOP else 'Race'}"
            mp_buttons.append(Button(pygame.Rect(220, 70, 230, 30), mode_txt, font_small, toggle_mode))

            mp_buttons.append(Button(pygame.Rect(220, 285, 140, 30), "Leave", font_small, lambda: (network.close(), rebuild_mp_menu()), color=(60, 60, 70)))

            def host_start_action():
                if not network.connected: return
                network.send_start_game()
                time.sleep(0.2)
                start_game(settings, window, canvas, font_small, font_med, font_big, player1_sprite, player2_sprite, enemy_sprite_dict, tile_surf, wall_surf, lb, network, network.role, mp_mode, mp_ip_input.text, network.role == ROLE_LOCAL_ONLY, bg_obj=night_bg)
            
            start_btn = Button(pygame.Rect(460, 285, 140, 30), "Start Match", font_small, host_start_action, accent=COL_ACCENT_2)
            if not network.connected:
                start_btn.disabled = True
                start_btn.text = "Waiting..."
            mp_buttons.append(start_btn)

        # ==============================
        # CONNECTED CLIENT LOBBY VIEW
        # ==============================
        elif network.role == ROLE_CLIENT and network.connected:
            # --- LEFT PANEL ---
            mp_buttons.append(Button(pygame.Rect(30, 70, 160, 40), "Room: CLIENT", font_med, None, color=COL_ACCENT_3))
            mp_buttons.append(Button(pygame.Rect(30, 170, 160, 30), "Disconnect", font_small, lambda: (network.close(), rebuild_mp_menu()), color=(60, 20, 20)))

            # --- RIGHT PANEL (Visuals only - Disabled/Overlayed) ---
            
            # Mode Toggle (Dummy - Visual only so it appears under the box)
            mode_txt = f"Mode: {'Co-op' if mp_mode == MODE_COOP else 'Race'}"
            dummy_mode = Button(pygame.Rect(220, 70, 230, 30), mode_txt, font_small, None) 
            dummy_mode.disabled = True # Disable interaction
            mp_buttons.append(dummy_mode)

            # Leave Button (Still functional for client)
            mp_buttons.append(Button(pygame.Rect(220, 285, 140, 30), "Leave", font_small, lambda: (network.close(), rebuild_mp_menu()), color=(60, 60, 70)))

            # Start Match (Dummy - Visual only)
            dummy_start = Button(pygame.Rect(460, 285, 140, 30), "Start Match", font_small, None, accent=COL_ACCENT_2)
            dummy_start.disabled = True
            mp_buttons.append(dummy_start)

        # ==============================
        # BROWSER VIEW (Disconnected)
        # ==============================
        else:
            # Left Panel
            mp_buttons.append(Button(pygame.Rect(30, 70, 160, 40), "Host Game", font_med, lambda: (network.host(), rebuild_mp_menu())))

            # Right Panel
            def toggle_mode():
                nonlocal mp_mode
                mp_mode = MODE_COOP if mp_mode == MODE_VERSUS else MODE_VERSUS
                rebuild_mp_menu()
            
            mode_txt = f"Mode: {'Co-op' if mp_mode == MODE_COOP else 'Race'}"
            mp_buttons.append(Button(pygame.Rect(220, 70, 230, 30), mode_txt, font_small, toggle_mode))

            def play_local():
                network.close() 
                start_game(settings, window, canvas, font_small, font_med, font_big, player1_sprite, player2_sprite, enemy_sprite_dict, tile_surf, wall_surf, lb, network, ROLE_LOCAL_ONLY, mp_mode, None, local_two_players=True, bg_obj=night_bg)
            mp_buttons.append(Button(pygame.Rect(460, 70, 140, 30), "Play Local", font_small, play_local, accent=COL_ACCENT_3))

            mp_ip_input.rect = pygame.Rect(220, 110, 220, 30)
            mp_buttons.append(Button(pygame.Rect(450, 110, 50, 30), "Paste", font_small, lambda: mp_ip_input.paste_text()))
            mp_buttons.append(Button(pygame.Rect(510, 110, 90, 30), "Connect", font_small, lambda: network.join(mp_ip_input.text.strip())))
            mp_ip_input.on_enter = lambda text: network.join(text.strip())

            def join_selected():
                target = selected_room
                if not target and mp_ip_input.text:
                    target = mp_ip_input.text.strip()
                    
                if target:
                    mp_ip_input.text = target
                    network.join(target)
                    
            btn_y = 285 
            mp_buttons.append(Button(pygame.Rect(220, btn_y, 230, 30), "Join Selected", font_small, join_selected))

            def refresh_action():
                nonlocal selected_room
                network.scanner.found_hosts.clear()
                room_list.clear()
                selected_room = None     # Unselect the item
                mp_ip_input.text = ""    # Clear the input box too since selection fills it
            
            mp_buttons.append(Button(pygame.Rect(460, btn_y, 140, 30), "Refresh", font_small, refresh_action))
            mp_buttons.append(Button(pygame.Rect(20, VIRTUAL_H - 50, 80, 30), "Back", font_small, lambda: (network.close(), set_state(STATE_MAIN_MENU))))

    def set_state(s):
        nonlocal game_state
        # IMPORTANT: Refresh save data whenever we change state (e.g. returning from game)
        # This ensures credits are updated in the UI immediately
        save_data.update(load_save_data())
        
        game_state = s
        if s == STATE_MAIN_MENU: rebuild_main_menu()
        elif s == STATE_SETTINGS: rebuild_settings_menu()
        elif s == STATE_SHOP: rebuild_shop_menu()
        elif s == STATE_MULTIPLAYER_MENU: 
            network.scanner.found_hosts = []
            rebuild_mp_menu()
    
    def stop(): nonlocal running; running = False

    rebuild_main_menu()
    rebuild_settings_menu()
    rebuild_mp_menu()
    
    host_sync_timer = 0.0
    last_connected_status = False

    while running:
        # CLAMP DT to prevent physics explosions on first frame or lag spikes
        dt = clock.tick(settings.target_fps) / 1000.0
        dt = min(dt, 0.05) # Max 0.05s per frame (20 FPS min physics speed)
        global_anim_timer += dt

        # Check Music Status (Restart if stopped by game and back in menu)
        if game_state in (STATE_MAIN_MENU, STATE_SETTINGS, STATE_SHOP, STATE_MULTIPLAYER_MENU, STATE_LEADERBOARD):
            if menu_music_loaded and not pygame.mixer.music.get_busy():
                pygame.mixer.music.play(-1)
        
        # Handle Window Scaling (Maintain Aspect Ratio)
        win_w, win_h = window.get_size()
        scale = min(win_w / VIRTUAL_W, win_h / VIRTUAL_H)
        scaled_w, scaled_h = int(VIRTUAL_W * scale), int(VIRTUAL_H * scale)
        offset_x, offset_y = (win_w - scaled_w) // 2, (win_h - scaled_h) // 2

        if game_state == STATE_MULTIPLAYER_MENU:
            network.scanner.listen()
            current_hosts = network.scanner.found_hosts
            if set(current_hosts) != set(room_list): room_list = list(current_hosts)
            if network.sock: network.poll_remote_state()
            if network.connected != last_connected_status:
                last_connected_status = network.connected
                rebuild_mp_menu()
            if network.role == ROLE_CLIENT and network.check_remote_start():
                start_game(settings, window, canvas, font_small, font_med, font_big, player1_sprite, player2_sprite, enemy_sprite_dict, tile_surf, wall_surf, lb, network, network.role, mp_mode, mp_ip_input.text, network.role == ROLE_LOCAL_ONLY, bg_obj=night_bg)
            if network.role == ROLE_HOST:
                host_sync_timer += dt
                if host_sync_timer > 0.5: 
                    network.send_lobby_mode(mp_mode)
                    host_sync_timer = 0
            elif network.role == ROLE_CLIENT:
                remote_mode = network.get_remote_lobby_mode()
                if remote_mode and remote_mode != mp_mode:
                    mp_mode = remote_mode
                    rebuild_mp_menu() 

        # Event Handling (Mouse coordinates adjusted for scale)
        for raw_event in pygame.event.get():
            if raw_event.type == pygame.QUIT: running = False
            elif raw_event.type == pygame.VIDEORESIZE:
                window = pygame.display.set_mode(raw_event.size, pygame.RESIZABLE)
            
            # Adjust mouse events to virtual resolution
            ui_event = raw_event
            if raw_event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                mx, my = raw_event.pos
                if offset_x <= mx < offset_x + scaled_w and offset_y <= my < offset_y + scaled_h:
                    vx, vy = (mx - offset_x) / scale, (my - offset_y) / scale
                    ui_event = pygame.event.Event(raw_event.type, {**raw_event.dict, "pos": (vx, vy)})
                else:
                    ui_event = pygame.event.Event(raw_event.type, {**raw_event.dict, "pos": (-9999, -9999)})

            if game_state == STATE_MAIN_MENU:
                for b in main_buttons: b.handle_event(ui_event)
            elif game_state == STATE_SHOP:
                for b in shop_buttons: b.handle_event(ui_event)
                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE: set_state(STATE_MAIN_MENU)
            elif game_state == STATE_SETTINGS:
                # UPDATED: Save settings only when exiting the menu
                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE: 
                    settings.save()
                    set_state(STATE_MAIN_MENU)
                if raw_event.type == pygame.MOUSEWHEEL: settings_scroll -= raw_event.y * 20
                sevt = ui_event
                if ui_event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and "pos" in ui_event.dict:
                    sevt = pygame.event.Event(ui_event.type, {**ui_event.dict, "pos": (ui_event.pos[0], ui_event.pos[1] + settings_scroll)})
                for w in settings_widgets: w.handle_event(sevt)
            elif game_state == STATE_MULTIPLAYER_MENU:
                
                # --- NEW: Handle Kick Confirmation Modal ---
                if show_kick_confirm:
                    if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE:
                        show_kick_confirm = False
                    
                    elif raw_event.type == pygame.MOUSEBUTTONDOWN and raw_event.button == 1:
                        if "pos" in ui_event.dict:
                            mx, my = ui_event.pos
                            
                            # Define Modal Rects (Center Screen)
                            modal_rect = pygame.Rect(VIRTUAL_W//2 - 120, VIRTUAL_H//2 - 60, 240, 120)
                            btn_yes = pygame.Rect(modal_rect.x + 20, modal_rect.bottom - 40, 90, 30)
                            btn_no = pygame.Rect(modal_rect.right - 110, modal_rect.bottom - 40, 90, 30)

                            if btn_yes.collidepoint(mx, my):
                                network.kick_client()
                                show_kick_confirm = False
                                rebuild_mp_menu() # Refresh UI to disable kick button
                            elif btn_no.collidepoint(mx, my):
                                show_kick_confirm = False
                            elif not modal_rect.collidepoint(mx, my):
                                # Clicked outside box -> Cancel
                                show_kick_confirm = False
                # -------------------------------------------
                
                else:
                    if ui_event.type == pygame.MOUSEBUTTONDOWN and ui_event.button == 1:
                        if "pos" in ui_event.dict:
                            mx, my = ui_event.pos
                            # Based on list_rect = pygame.Rect(220, 170, 380, 80)
                            # Row height = 24
                            if 220 <= mx <= 600 and 170 <= my <= 250:
                                index = int((my - 170) / 24)
                                if 0 <= index < len(room_list) and (170 + index * 24 <= 240):
                                    selected_room = room_list[index]
                                    mp_ip_input.text = selected_room # Autofill input box


                    for b in mp_buttons: b.handle_event(ui_event)
                    mp_ip_input.handle_event(ui_event)

        if game_state == STATE_SETTINGS:
            if settings_widgets:
                max_bottom = max([w.rect.bottom for w in settings_widgets])
                max_scroll = max(0, max_bottom + 20 - VIRTUAL_H)
                settings_scroll = clamp(settings_scroll, 0, max_scroll)
        elif game_state == STATE_MULTIPLAYER_MENU: mp_ip_input.update(dt)

        # Rendering
        canvas.fill(COL_BG) # Clear with BG
        
        if game_state == STATE_MAIN_MENU:
            menu_scroll_x += dt * 60 # Auto scroll right
            day_bg.draw(canvas, menu_scroll_x) # Use Day Parallax
            draw_text_shadow(canvas, font_big, GAME_TITLE, VIRTUAL_W//2, 60, center=True, pulse=True, time_val=global_anim_timer)
            for b in main_buttons: b.draw(canvas, dt)
        
        elif game_state == STATE_SHOP:
            draw_text_shadow(canvas, font_big, "Cybernetic Upgrades", 20, 20, col=COL_ACCENT_3)
            
            # Draw Credits
            c_str = f"CREDITS: {int(save_data['credits'])}"
            c_sz = font_med.size(c_str)
            draw_panel(canvas, pygame.Rect(VIRTUAL_W - c_sz[0] - 30, 20, c_sz[0] + 20, 30))
            draw_text_shadow(canvas, font_med, c_str, VIRTUAL_W - c_sz[0] - 20, 25, col=COL_ACCENT_3)

            y_start = 70
            row_height = 65 

            for i, (key, info) in enumerate(UPGRADE_INFO.items()):
                lvl = save_data["upgrades"].get(key, 0)
                row_y = y_start + i * row_height
                draw_panel(canvas, pygame.Rect(20, row_y, VIRTUAL_W - 40, 50))
                draw_text_shadow(canvas, font_med, f"{info['name']} (Lvl {lvl}/{info['max']})", 35, row_y + 8, col=COL_ACCENT_1)
                draw_text_shadow(canvas, font_small, info['desc'], 35, row_y + 30, col=(180, 180, 200))

            for b in shop_buttons: b.draw(canvas, dt)

        elif game_state == STATE_SETTINGS:
            draw_text_shadow(canvas, font_big, "System Config", 20, 20)
            for w in settings_widgets:
                orig_y = w.rect.y
                w.rect.y = orig_y - settings_scroll
                if w.rect.bottom > 0 and w.rect.top < VIRTUAL_H: w.draw(canvas)
                w.rect.y = orig_y
            
            back_hint = font_small.render("[ESC] Return", False, (100, 100, 100))
            canvas.blit(back_hint, (10, VIRTUAL_H - 20))

        elif game_state == STATE_MULTIPLAYER_MENU:
            draw_text_shadow(canvas, font_big, "Network Lobby", 20, 20)
            
            draw_panel(canvas, pygame.Rect(20, 60, 180, 260)) # Left Panel
            draw_panel(canvas, pygame.Rect(210, 60, 400, 260)) # Right Panel
            
            # ==============================
            # DRAWING: HOST OR CONNECTED CLIENT
            # ==============================
            if network.role == ROLE_HOST or (network.role == ROLE_CLIENT and network.connected):
                # Draw Header
                header_text = "Connected Players:"
                canvas.blit(font_small.render(header_text, False, COL_ACCENT_1), (220, 115))
                
                # Player List Box
                list_rect = pygame.Rect(220, 135, 380, 115)
                pygame.draw.rect(canvas, (10, 10, 20), list_rect)
                pygame.draw.rect(canvas, COL_UI_BORDER, list_rect, 1)

                # Player Names
                p1_text = "1. You (Host)" if network.role == ROLE_HOST else "1. Host"
                p1_col = COL_ACCENT_3 if network.role == ROLE_HOST else COL_ACCENT_2
                canvas.blit(font_small.render(p1_text, False, p1_col), (225, 140))

                if network.connected:
                    p2_text = "2. Player 2" if network.role == ROLE_HOST else "2. You (Client)"
                    p2_col = COL_ACCENT_2 if network.role == ROLE_HOST else COL_ACCENT_3
                    canvas.blit(font_small.render(p2_text, False, p2_col), (225, 160))
                else:
                    canvas.blit(font_small.render("2. ... Waiting for player ...", False, (100, 100, 100)), (225, 160))

                # --- OVERLAY FOR CLIENTS (THE REQUESTED FEATURE) ---
                if network.role == ROLE_CLIENT and network.connected:
                    # 1. Overlay for the Mode Toggle (Top Right)
                    overlay_mode = pygame.Surface((230, 30))
                    overlay_mode.set_alpha(180) # Semi-transparent
                    overlay_mode.fill((20, 20, 20)) # Dark box
                    canvas.blit(overlay_mode, (220, 70))
                    
                    # 2. Overlay for the Start Button (Bottom Right)
                    overlay_start = pygame.Surface((140, 30))
                    overlay_start.set_alpha(180)
                    overlay_start.fill((20, 20, 20))
                    canvas.blit(overlay_start, (460, 285))

                    # 3. "HOST ONLY" Text
                    # Draw centered on Mode button
                    draw_text_shadow(canvas, font_small, "HOST ONLY", 220 + 115, 70 + 8, center=True, col=(200, 50, 50))
                    # Draw centered on Start button
                    draw_text_shadow(canvas, font_small, "HOST ONLY", 460 + 70, 285 + 8, center=True, col=(200, 50, 50))

            # ==============================
            # DRAWING: BROWSER VIEW (Disconnected)
            # ==============================
            else:
                canvas.blit(font_small.render("LAN Hosts:", False, COL_ACCENT_1), (220, 150))
                
                # Browser List Box
                list_rect = pygame.Rect(220, 170, 380, 80)
                pygame.draw.rect(canvas, (10, 10, 20), list_rect)
                pygame.draw.rect(canvas, COL_UI_BORDER, list_rect, 1)
                
                if not room_list:
                    canvas.blit(font_small.render("Scanning network...", False, (80, 80, 90)), (230, 180))
                else:
                    for i, ip in enumerate(room_list):
                        y_pos = 170 + i * 24
                        if y_pos > 240: break
                        row_rect = pygame.Rect(220, y_pos, 380, 20)
                        if ip == selected_room:
                            pygame.draw.rect(canvas, (40, 40, 60), row_rect)
                        elif row_rect.collidepoint(pygame.mouse.get_pos()[0] - offset_x, pygame.mouse.get_pos()[1] - offset_y): 
                             pygame.draw.rect(canvas, (30, 30, 40), row_rect)
                        canvas.blit(font_small.render(f"HOST: {ip}", False, COL_TEXT), (225, y_pos + 2))

                mp_ip_input.draw(canvas)

            # Status Text positioned safely at y=260 (between list box and bottom buttons)
            status_col = (100, 255, 100) if network.connected else (100, 100, 100)
            status_txt = "STATUS: CONNECTED" if network.connected else "STATUS: OFFLINE"
            if network.role == ROLE_HOST: status_txt = "STATUS: HOSTING (LOBBY)"
            elif network.role == ROLE_CLIENT: status_txt += " (CLIENT)"
            
            draw_text_shadow(canvas, font_small, status_txt, 220, 260, col=status_col)

            for b in mp_buttons: b.draw(canvas, dt)
            
            if show_kick_confirm:
                # 1. Dark Overlay
                overlay = pygame.Surface((VIRTUAL_W, VIRTUAL_H), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                canvas.blit(overlay, (0, 0))

                # 2. The Box
                modal_rect = pygame.Rect(VIRTUAL_W//2 - 120, VIRTUAL_H//2 - 60, 240, 120)
                draw_panel(canvas, modal_rect, color=(30, 10, 10), border=(255, 50, 50))

                # 3. Text
                draw_text_shadow(canvas, font_med, "KICK PLAYER?", modal_rect.centerx, modal_rect.y + 20, center=True, col=(255, 100, 100))
                draw_text_shadow(canvas, font_small, "Are you sure?", modal_rect.centerx, modal_rect.y + 45, center=True)

                # 4. Buttons (Manual draw for simplicity, or use Button class)
                # Yes Button
                yes_rect = pygame.Rect(modal_rect.x + 20, modal_rect.bottom - 40, 90, 30)
                is_hover_yes = yes_rect.collidepoint(pygame.mouse.get_pos()[0]/scale - offset_x/scale, pygame.mouse.get_pos()[1]/scale - offset_y/scale)
                pygame.draw.rect(canvas, (180, 20, 20) if is_hover_yes else (120, 20, 20), yes_rect, border_radius=4)
                pygame.draw.rect(canvas, (255, 100, 100), yes_rect, 2, border_radius=4)
                txt_yes = font_small.render("YES", False, COL_TEXT)
                canvas.blit(txt_yes, txt_yes.get_rect(center=yes_rect.center))

                # No Button
                no_rect = pygame.Rect(modal_rect.right - 110, modal_rect.bottom - 40, 90, 30)
                is_hover_no = no_rect.collidepoint(pygame.mouse.get_pos()[0]/scale - offset_x/scale, pygame.mouse.get_pos()[1]/scale - offset_y/scale)
                pygame.draw.rect(canvas, (60, 60, 70) if is_hover_no else (40, 40, 50), no_rect, border_radius=4)
                pygame.draw.rect(canvas, (100, 100, 120), no_rect, 2, border_radius=4)
                txt_no = font_small.render("CANCEL", False, COL_TEXT)
                canvas.blit(txt_no, txt_no.get_rect(center=no_rect.center))

        # Scale and Draw to Window
        window.fill((0, 0, 0)) # Letterbox bars
        scaled_surf = pygame.transform.scale(canvas, (scaled_w, scaled_h))
        window.blit(scaled_surf, (offset_x, offset_y))
        pygame.display.flip()

    network.close()
    pygame.quit()

def apply_screen_mode(window, mode_index):
    w, h = window.get_size()
    if mode_index == MODE_WINDOW: pygame.display.set_mode((w, h), pygame.RESIZABLE)
    elif mode_index == MODE_FULLSCREEN: pygame.display.set_mode((w, h), pygame.FULLSCREEN)
    elif mode_index == MODE_BORDERLESS: pygame.display.set_mode((w, h), pygame.NOFRAME | pygame.FULLSCREEN)

# =========================
# GAME SESSION
# =========================
def start_game(settings, window, canvas, font_small, font_med, font_big, player1_sprites, player2_sprites, enemy_sprite_dict, tile_surf, wall_surf, lb, network, net_role, mode, mp_name_hint=None, local_two_players=False, bg_obj=None):
    clock = pygame.time.Clock()
    
    # Stop Menu Music
    if pygame.mixer.get_init():
        pygame.mixer.music.stop()

    local_data = load_save_data()
    local_stats = local_data["upgrades"]

    game_seed = 0
    if net_role == ROLE_HOST or net_role == ROLE_LOCAL_ONLY:
        game_seed = random.randint(1, 999999)
        random.seed(game_seed)
    else:
        game_seed = 0 
        random.seed(game_seed)

    level = LevelManager(tile_surf, enemy_sprite_dict, game_seed) 
    particles.clear()
    floating_texts.clear()
    
    # Start on the left, on ground level
    spawn_x = 100
    spawn_y = GROUND_LEVEL - 60
    
    stats_p1 = local_stats if (net_role != ROLE_CLIENT) else None 
    stats_p2 = local_stats if (net_role != ROLE_HOST) else None
    if net_role == ROLE_LOCAL_ONLY:
        stats_p1 = local_stats
        stats_p2 = local_stats

    # Pass sprites to Player Constructor
    p1 = Player(COL_ACCENT_1, spawn_x, spawn_y, stats_p1, sprite_dict=player1_sprites)
    p2 = Player(COL_ACCENT_2, spawn_x - 30, spawn_y, stats_p2, sprite_dict=player2_sprites)
    base_x = spawn_x

    if net_role == ROLE_CLIENT: local_player, remote_player = p2, p1
    else: local_player, remote_player = p1, p2
    
    p1_local = (net_role in (ROLE_HOST, ROLE_LOCAL_ONLY))
    p2_local = (net_role == ROLE_CLIENT) or (net_role == ROLE_LOCAL_ONLY and local_two_players)
    use_p1 = True
    use_p2 = (mode != MODE_SINGLE)

    # Initial Camera Setup
    cam_x = p1.x - 200 # Offset so player is on left side
    cam_y = 0
    cam_x_p1, cam_x_p2 = cam_x, cam_x
    cam_y_p1, cam_y_p2 = cam_y, cam_y
    
    view1_surf = pygame.Surface((VIRTUAL_W // 2, VIRTUAL_H))
    view2_surf = pygame.Surface((VIRTUAL_W // 2, VIRTUAL_H))

    distance, elapsed = 0.0, 0.0
    running, game_over = True, False
    winner_text = ""
    p1_distance, p2_distance = 0.0, 0.0
    p1_orbs, p2_orbs = 0, 0
    lb_key = {MODE_SINGLE: "single", MODE_COOP: "coop", MODE_VERSUS: "versus"}[mode]
    screen_shake_timer = 0.0
    session_credits = 0.0
    waiting_for_seed = (net_role == ROLE_CLIENT)

    def render_scene(target_surf, cam_x_now, cam_y_now, highlight_player=None):
        # Use Parallax Background logic (horizontal scroll)
        if bg_obj:
            bg_obj.draw(target_surf, cam_x_now)
        else:
            draw_gradient_background(target_surf, level.current_stage)
        
        if waiting_for_seed:
            txt = font_med.render("SYNCING MAP DATA...", False, COL_ACCENT_1)
            target_surf.blit(txt, txt.get_rect(center=(target_surf.get_width()//2, target_surf.get_height()//2)))
            return

        level.draw(target_surf, cam_x_now, cam_y_now)
        for p in particles: p.draw(target_surf, cam_x_now, cam_y_now)

        def draw_floating_cd(pl):
            # Only draw if cooldown is active
            if pl.slam_cooldown > 0:
                # Position relative to camera
                sx = pl.x - cam_x_now
                sy = pl.y - cam_y_now
                
                # Draw just above the player
                bar_w = pl.w
                bar_h = 4
                bar_y = sy - 8 
                
                # Background (Black)
                pygame.draw.rect(target_surf, (0,0,0), (sx, bar_y, bar_w, bar_h))
                
                # Foreground (White/Silver shrinking bar)
                ratio = pl.slam_cooldown / pl.slam_cd_val
                fill_w = int(bar_w * ratio)
                pygame.draw.rect(target_surf, (200, 200, 200), (sx, bar_y, fill_w, bar_h))

        if use_p1: 
            p1.draw(target_surf, cam_x_now, cam_y_now)
            draw_floating_cd(p1)

        if use_p2: 
            p2.draw(target_surf, cam_x_now, cam_y_now)
            draw_floating_cd(p2)

        for ft in floating_texts: ft.draw(target_surf, cam_x_now, cam_y_now)

        p1_total = int(p1_distance / 10 + p1_orbs * 100)
        p2_total = int(p2_distance / 10 + p2_orbs * 100)
        
        # HUD Panel (Top Left Stats)
        draw_panel(target_surf, pygame.Rect(5, 5, 120, 50), color=(0, 0, 0, 100))
        target_surf.blit(font_small.render(f"DIST: {int(distance/10)}m", False, COL_TEXT), (10, 10))
        target_surf.blit(font_small.render(f"STAGE: {level.current_stage}", False, COL_TEXT), (10, 28))
        
        hud_y = 65
        
        def draw_player_hud(pl, name, y_pos, is_highlighted):
            panel_col = (30, 30, 50) if is_highlighted else (10, 10, 20)
            draw_panel(target_surf, pygame.Rect(5, y_pos, 150, 24), color=panel_col)
            target_surf.blit(font_small.render(name, False, COL_TEXT), (10, y_pos+4))

            # Segmented HP Bar
            bar_x = 40
            bar_y = y_pos + 6
            total_bar_w = 100
            bar_h = 10
            pygame.draw.rect(target_surf, (40, 40, 40), (bar_x, bar_y, total_bar_w, bar_h))
            
            hp_col = (255, 50, 50) if pl.hp <= 1 else (50, 255, 50)
            seg_w = (total_bar_w / pl.max_hp) if pl.max_hp > 0 else total_bar_w

            for i in range(pl.hp):
                rect_x = bar_x + (i * seg_w)
                rect_w = seg_w - 1 if (i < pl.max_hp - 1) else seg_w
                if rect_w > 0:
                    pygame.draw.rect(target_surf, hp_col, (rect_x, bar_y, rect_w, bar_h))

            # PTS (Top Right)
            score_val = p1_total if pl == p1 else p2_total
            score_str = f"PTS {score_val}"
            score_surf = font_small.render(score_str, False, COL_ACCENT_3)
            score_x = target_surf.get_width() - score_surf.get_width() - 15
            score_bg_rect = pygame.Rect(score_x - 5, y_pos, score_surf.get_width() + 10, 24)
            draw_panel(target_surf, score_bg_rect, color=(0, 0, 0, 150))
            target_surf.blit(score_surf, (score_x, y_pos + 4))

        if use_p1:
            draw_player_hud(p1, "P1", hud_y, highlight_player == 1)
            hud_y += 30 
        if use_p2:
            draw_player_hud(p2, "P2", hud_y, highlight_player == 2)

    while running:
        # CLAMP DT to prevent physics explosions on first frame or lag spikes
        dt = clock.tick(settings.target_fps) / 1000.0
        dt = min(dt, 0.05) # Max 0.05s per frame (20 FPS min physics speed)

        if not game_over and not waiting_for_seed: elapsed += dt
        
        for p in particles: p.update(dt)
        particles[:] = [p for p in particles if p.life > 0]
        for ft in floating_texts: ft.update(dt)
        floating_texts[:] = [ft for ft in floating_texts if ft.life > 0]
        
        shake_x, shake_y = 0, 0
        if screen_shake_timer > 0:
            screen_shake_timer -= dt
            if screen_shake_timer > 0:
                shake_x = random.randint(-3, 3)
                shake_y = random.randint(-3, 3)

        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False; return
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: running = False; return
            elif event.type == pygame.VIDEORESIZE: window = pygame.display.set_mode(event.size, pygame.RESIZABLE)

        keys = pygame.key.get_pressed()
        if net_role != ROLE_LOCAL_ONLY:
            network.poll_remote_state()
            flag, text = network.consume_remote_game_over()
            if flag and not game_over: game_over = True; winner_text = text

        if not game_over:
            if net_role != ROLE_LOCAL_ONLY:
                # Use Horizontal Distance for score sync
                lt = int(p1_distance/10 + p1_orbs * 100) if local_player is p1 else int(p2_distance/10 + p2_orbs * 100)
                send_seed = game_seed if net_role == ROLE_HOST else 0
                network.send_local_state(local_player.x, local_player.y, local_player.alive, lt, send_seed, local_player.hp)
                network.poll_remote_state()
                rstate = network.get_remote_state()
                remote_player.x, remote_player.y, remote_player.alive = rstate["x"], rstate["y"], rstate["alive"]
                remote_player.hp = rstate.get("hp", 3)
                if waiting_for_seed and rstate["seed"] != 0:
                    game_seed = rstate["seed"]
                    level = LevelManager(tile_surf, enemy_sprite_dict, game_seed)
                    waiting_for_seed = False 

            if not waiting_for_seed:
                distance = max(distance, p1_distance, p2_distance)
                difficulty = clamp(distance / 5000.0, 0.0, 1.0) # Adjusted for horizontal scale
                
                # --- UPDATE PLAYERS ---
                if mode == MODE_SINGLE or net_role != ROLE_LOCAL_ONLY:
                    local_player.update(dt, level, keys[pygame.K_LEFT] or keys[pygame.K_a], keys[pygame.K_RIGHT] or keys[pygame.K_d], keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w], keys[pygame.K_LSHIFT] or keys[pygame.K_s] or keys[pygame.K_DOWN])
                else:
                    if p1_local and use_p1: p1.update(dt, level, keys[pygame.K_a], keys[pygame.K_d], keys[pygame.K_w] or keys[pygame.K_SPACE], keys[pygame.K_LSHIFT] or keys[pygame.K_s])
                    if p2_local and use_p2: p2.update(dt, level, keys[pygame.K_j], keys[pygame.K_l], keys[pygame.K_i], keys[pygame.K_RSHIFT] or keys[pygame.K_k])

                # --- CAMERA UPDATE (HORIZONTAL) ---
                if mode == MODE_VERSUS and net_role == ROLE_LOCAL_ONLY and use_p1 and use_p2:
                    # Split screen cam logic
                    tx1 = p1.x if p1.alive else (p2.x if p2.alive else p1.x)
                    tx2 = p2.x if p2.alive else (p1.x if p1.alive else p2.x)
                    
                    cam_x_p1 += ((tx1 - 200) - cam_x_p1) * 0.1
                    cam_x_p2 += ((tx2 - 200) - cam_x_p2) * 0.1
                    
                    cam_y_p1 = 0 
                    cam_y_p2 = 0
                    cam_x = max(cam_x_p1, cam_x_p2)
                else:
                    # Single/Network Cam
                    if mode == MODE_SINGLE: b_x = local_player.x
                    elif net_role != ROLE_LOCAL_ONLY:
                        if local_player.alive: b_x = local_player.x
                        elif remote_player.alive: b_x = remote_player.x
                        else: b_x = local_player.x
                    else:
                        if p1.alive and p2.alive: b_x = max(p1.x, p2.x)
                        elif p1.alive: b_x = p1.x
                        elif p2.alive: b_x = p2.x
                        else: b_x = p1.x
                    
                    cam_x += ((b_x - 200) - cam_x) * 0.1
                    cam_y = 0 # Lock Y axis for horizontal feel, or clamp it
                
                # --- UPDATE LEVEL ---
                cam_rect = pygame.Rect(int(cam_x), int(cam_y), VIRTUAL_W, VIRTUAL_H)
                level.update(dt, cam_x, difficulty)
                
                spike_deaths = level.update_enemies(dt, [p for p in [p1, p2] if (use_p1 if p==p1 else use_p2)], cam_rect)
                for dx, dy in spike_deaths: level.spawn_credit(dx, dy, 0.5)
                
                # Update Distance Score
                if use_p1 and p1.alive and (net_role in (ROLE_LOCAL_ONLY, ROLE_HOST)): p1_distance = max(p1_distance, p1.x - base_x)
                if use_p2 and p2.alive and (net_role in (ROLE_LOCAL_ONLY, ROLE_CLIENT)): p2_distance = max(p2_distance, p2.x - base_x)

                players_to_check = []
                if net_role == ROLE_LOCAL_ONLY:
                    if use_p1 and p1.alive: players_to_check.append(p1)
                    if use_p2 and p2.alive: players_to_check.append(p2)
                else:
                    if local_player.alive: players_to_check.append(local_player)
                
                for credit in level.dropped_credits[:]:
                    c_rect = credit.rect()
                    for p in players_to_check:
                        if p.rect().colliderect(c_rect):
                            session_credits += credit.value
                            spawn_credit_text(credit.x, credit.y, credit.value, font_small)
                            if credit in level.dropped_credits: level.dropped_credits.remove(credit)
                            break

                for orb in level.orbs[:]:
                    # Check Player 1
                    if use_p1 and p1.alive and p1.rect().colliderect(orb): 
                        p1_orbs += 1
                        # Spawn the text
                        floating_texts.append(FloatingText(orb.x, orb.y, "+100 PTS", font_small, COL_ACCENT_3))
                        level.orbs.remove(orb)
                        continue
                    
                    # Check Player 2
                    if use_p2 and p2.alive and p2.rect().colliderect(orb): 
                        p2_orbs += 1
                        # Spawn the text
                        floating_texts.append(FloatingText(orb.x, orb.y, "+100 PTS", font_small, COL_ACCENT_3))
                        level.orbs.remove(orb)

                def resolve_slam(player):
                    if not player.pending_slam_impact: return
                    player.pending_slam_impact = False
                    nonlocal screen_shake_timer
                    if player.slam_impact_power > 150: screen_shake_timer = 0.2
                    radius = SLAM_BASE_RADIUS + player.slam_impact_power * SLAM_RADIUS_PER_HEIGHT
                    cx, cy = player.x + player.w / 2, player.y + player.h
                    
                    player.invul_timer = 0.5 
                    player.flash_on_invul = False
                    
                    for e in level.enemies:
                        if not e.alive: continue
                        ex, ey = e.x + e.w / 2, e.y + e.h / 2
                        
                        # Radial Collision check
                        if (ex - cx)**2 + (ey - cy)**2 <= radius**2: 
                             damage = 1.0 # Default damage
                             
                             # If it is NOT a boss, set damage to current HP (Insta-Kill)
                             if not getattr(e, 'is_boss', False):
                                 damage = e.max_hp 

                             died = e.take_damage(damage)

                             if died:
                                 level.spawn_credit(e.x, e.y, 1.0)
                             else:
                                 # Visual feedback for hit
                                 spawn_dust(e.x + e.w/2, e.y, 3, (255, 100, 100))

                def handle_collisions_for_player(player):
                    if not player.alive or player.is_dying: return
                    
                    # Falling into void deals 1 HP and Teleports back
                    if player.y > VIRTUAL_H + 200: 
                        player.take_damage(1)
                        if player.alive:
                            # Teleport to last safe ground
                            player.x = player.last_safe_x
                            player.y = player.last_safe_y - TILE_SIZE 
                            player.vx = 0
                            player.vy = 0
                            player.slam_active = False
                        return
                    
                    r = player.rect()
                    # Obstacle Collisions
                    for obs in level.obstacles: 
                        if r.colliderect(obs): 
                            player.take_damage(1, source_x=obs.centerx) 
                            return
                    
                    # Enemy Collisions
                    for e in level.enemies: 
                        if r.colliderect(e.rect()): 
                            player_bottom = player.y + player.h
                            enemy_center = e.y + e.h * 0.5
                            is_above = player_bottom < enemy_center + 5
                            is_falling = player.vy > 0
                            
                            if player.slam_active or (is_falling and is_above):
                                damage = 0.5
                                
                                if player.slam_active:
                                    # If active slam AND not a boss -> Insta Kill
                                    if not getattr(e, 'is_boss', False):
                                        damage = e.max_hp
                                    else:
                                        damage = 1.0 # Standard damage for boss
                                # ----------------------------
                                
                                died = e.take_damage(damage)
                                player.vy = -700.0 
                                player.invul_timer = 0.2 
                                player.flash_on_invul = False 
                                
                                player.slam_cooldown = 0 
                                player.slam_active = False 
                                
                                if died:
                                    level.spawn_credit(e.x, e.y, 1.0) 
                                else:
                                    spawn_dust(e.x + e.w/2, e.y, 3, (255, 50, 50))
                            
                            # --- PLAYER HIT LOGIC ---
                            else: 
                                if e.invul_timer > 0:
                                    return
                                    
                                player.take_damage(1, source_x=(e.x + e.w/2))
                            return

                if net_role == ROLE_LOCAL_ONLY:
                    if p1_local and use_p1: handle_collisions_for_player(p1)
                    if p2_local and use_p2: handle_collisions_for_player(p2)
                else: handle_collisions_for_player(local_player)
                
                if use_p1: resolve_slam(p1)
                if use_p2: resolve_slam(p2)
                level.enemies = [e for e in level.enemies if e.alive]

                p1_total = int(p1_distance/10 + p1_orbs * 100)
                p2_total = int(p2_distance/10 + p2_orbs * 100)
                
                def finish(name, score, txt):
                    nonlocal game_over, winner_text
                    game_over = True
                    winner_text = txt
                    add_score(lb, lb_key, name, score)
                    if session_credits > 0:
                        local_data["credits"] += session_credits
                        save_save_data(local_data)
                    if net_role != ROLE_LOCAL_ONLY: network.send_game_over(winner_text)

                if mode == MODE_SINGLE and not local_player.alive:
                        finish("Player", p1_total if local_player is p1 else p2_total, "GAME OVER")
                elif mode == MODE_COOP and not p1.alive and not p2.alive:
                        finish("Team", min(p1_total, p2_total), "MISSION FAILED")
                elif mode == MODE_VERSUS and not p1.alive and not p2.alive:
                        winner = "DRAW" if p1_total == p2_total else ("P1 WINS" if p1_total > p2_total else "P2 WINS")
                        finish(winner, max(p1_total, p2_total), winner)

        canvas.fill(COL_BG)
        final_cam_x = cam_x + shake_x
        final_cam_y = cam_y + shake_y

        if mode == MODE_VERSUS and net_role == ROLE_LOCAL_ONLY and use_p1 and use_p2:
            render_scene(view1_surf, cam_x_p1, cam_y_p1, highlight_player=1)
            render_scene(view2_surf, cam_x_p2, cam_y_p2, highlight_player=2)
            half_w = VIRTUAL_W // 2
            canvas.blit(view1_surf, (0, 0))
            canvas.blit(view2_surf, (half_w, 0))
            pygame.draw.line(canvas, COL_UI_BORDER, (half_w, 0), (half_w, VIRTUAL_H), 4)
        else:
            render_scene(canvas, final_cam_x, final_cam_y, highlight_player=None)

        if game_over:
            overlay = pygame.Surface((VIRTUAL_W, VIRTUAL_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            canvas.blit(overlay, (0, 0))
            
            draw_text_shadow(canvas, font_big, winner_text, VIRTUAL_W//2, VIRTUAL_H//2 - 40, center=True, col=COL_ACCENT_3)
            draw_text_shadow(canvas, font_med, f"CREDITS EARNED: {int(session_credits)}", VIRTUAL_W//2, VIRTUAL_H//2, center=True)
            draw_text_shadow(canvas, font_small, "PRESS ESC TO RETURN", VIRTUAL_W//2, VIRTUAL_H//2 + 30, center=True)
            
            y = VIRTUAL_H // 2 + 60
            canvas.blit(font_small.render("LEADERBOARD:", False, (150, 150, 150)), (VIRTUAL_W // 2 - 40, y))
            y += 16
            for i, e in enumerate(lb[lb_key][:3]):
                canvas.blit(font_small.render(f"{i+1}. {e['name']} - {e['score']}", False, (200, 200, 200)), (VIRTUAL_W // 2 - 60, y))
                y += 14

        win_w, win_h = window.get_size()
        scale = min(win_w / VIRTUAL_W, win_h / VIRTUAL_H)
        scaled_w, scaled_h = int(VIRTUAL_W * scale), int(VIRTUAL_H * scale)
        offset_x, offset_y = (win_w - scaled_w) // 2, (win_h - scaled_h) // 2
        
        window.fill((0, 0, 0))
        surf_scaled = pygame.transform.scale(canvas, (scaled_w, scaled_h))
        window.blit(surf_scaled, (offset_x, offset_y))
        pygame.display.flip()

if __name__ == "__main__":
    main()