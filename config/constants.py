"""
Game constants, colors, physics, and configuration values.
"""
import os
import pygame

# =========================
# CONFIG / CONSTANTS
# =========================
GAME_TITLE = "Get slimed"

# =========================
# BOSS FIGHT CONSTANTS
# =========================
PORTAL_SPAWN_DISTANCE = 10000  # X position where portal spawns

# Boss constants
BOSS_HP = 5
ATTACK_DURATION_MIN = 15.0
ATTACK_DURATION_MAX = 20.0
TIRED_DURATION = 4.0
BOSS_FLIGHT_HEIGHT = 20  # Height above platforms when flying
BOSS_TIRED_HEIGHT = 300  # Height boss descends to when tired
ENRAGE_ATTACK_SPEED_MULTIPLIER = 1.25  # 25% faster at 1 HP

# Boss room dimensions
BOSS_ROOM_WIDTH = 640  # Same as VIRTUAL_W
BOSS_ROOM_HEIGHT = 480  # Same as VIRTUAL_H

# Rewards
VICTORY_SCORE = 500
VICTORY_CREDITS = 5

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

# Dash Constants
BASE_DASH_SPEED = 800.0
BASE_DASH_DURATION = 0.20
BASE_DASH_COOLDOWN = 1.2

TILE_SIZE = 20 
# Ground level for horizontal play
GROUND_LEVEL = VIRTUAL_H - 2 * TILE_SIZE

# Stage configurations (Distance in pixels)
STAGE_1_END = 4000
STAGE_2_END = 9000
# Stage 3 is Endless (anything > STAGE_2_END)

# Path helpers
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
STATE_CONTROLS = "controls"
STATE_GAME = "game"
STATE_MULTIPLAYER_MENU = "mp_menu"
STATE_MP_LOBBY = "mp_lobby"  # Create/Join choice
STATE_MP_MODE = "mp_mode"  # Local/LAN choice
STATE_MP_CHARACTER_SELECT = "mp_char_select"  # 2-player character select
STATE_MP_ROOM_BROWSER = "mp_room_browser"  # Server list for joining
STATE_LEADERBOARD = "leaderboard"
STATE_SHOP = "shop"
STATE_CHARACTER_SELECT = "character_select"

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

# Character Selection
CHARACTER_COLORS = [
    {"name": "Pink", "row": 0},
    {"name": "Red", "row": 1},
    {"name": "Orange", "row": 2},
    {"name": "Blue", "row": 3},
    {"name": "Green", "row": 4},
    {"name": "Brown", "row": 5},
    {"name": "Grey", "row": 6}
]

CHARACTER_ABILITIES = [
    {"name": "Slam", "description": "Instantly slam down, dealing\nmassive damage to enemies below"},
    {"name": "Dash", "description": "Dash forward at high speed,\nphasing through enemies and spikes"}
]

# DEFAULT KEYBINDINGS (will be initialized after pygame.init())
DEFAULT_KEYBINDS = None

def init_default_keybinds():
    """Initialize keybinds after pygame is initialized"""
    global DEFAULT_KEYBINDS
    DEFAULT_KEYBINDS = {
        "p1_left": pygame.K_a,
        "p1_right": pygame.K_d,
        "p1_jump": pygame.K_w,
        "p1_slam": pygame.K_s,
        "p2_left": pygame.K_j,
        "p2_right": pygame.K_l,
        "p2_jump": pygame.K_i,
        "p2_slam": pygame.K_k
    }
    return DEFAULT_KEYBINDS
