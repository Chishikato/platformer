"""
Main Menu - game entry point and menu system.
"""
import os
import time
import pygame

from config.constants import (
    VIRTUAL_W, VIRTUAL_H, GAME_TITLE,
    COL_BG, COL_TEXT, COL_UI_BG, COL_UI_BORDER,
    COL_ACCENT_1, COL_ACCENT_2, COL_ACCENT_3,
    STATE_MAIN_MENU, STATE_SETTINGS, STATE_CONTROLS, STATE_SHOP, STATE_LEADERBOARD,
    STATE_CHARACTER_SELECT, STATE_MULTIPLAYER_MENU,
    STATE_MP_LOBBY, STATE_MP_MODE, STATE_MP_CHARACTER_SELECT, STATE_MP_ROOM_BROWSER,
    MODE_WINDOW, MODE_FULLSCREEN, MODE_BORDERLESS,
    MODE_SINGLE, MODE_COOP, MODE_VERSUS,
    ROLE_LOCAL_ONLY, ROLE_HOST, ROLE_CLIENT,
    CHARACTER_COLORS, CHARACTER_ABILITIES, DEFAULT_KEYBINDS,
    get_asset_path, init_default_keybinds
)
from config.settings import Settings
from core.helpers import draw_text_shadow, draw_panel
from core.data_persistence import (
    load_leaderboard, load_save_data, save_save_data, UPGRADE_INFO, get_upgrade_cost
)
from ui.button import Button
from ui.slider import Slider
from ui.toggle import Toggle
from ui.text_input import TextInput
from ui.keybind_button import KeybindButton
from ui.section_header import SectionHeader
from effects.background import ParallaxBackground
from networking.network_manager import NetworkManager
from assets.loaders import (
    load_sprite_sheet, make_tile_surface, make_wall_surface,
    load_character_sprites, draw_character_preview
)
from game.game_session import start_game


def apply_screen_mode(window, mode_index):
    """Apply screen mode (windowed/fullscreen/borderless)."""
    w, h = window.get_size()
    if mode_index == MODE_WINDOW: 
        pygame.display.set_mode((w, h), pygame.RESIZABLE)
    elif mode_index == MODE_FULLSCREEN: 
        pygame.display.set_mode((w, h), pygame.FULLSCREEN)
    elif mode_index == MODE_BORDERLESS: 
        pygame.display.set_mode((w, h), pygame.NOFRAME | pygame.FULLSCREEN)


def main():
    """Main game entry point - handles menus and game state."""
    pygame.init()
    pygame.mixer.init()

    settings = Settings()
    settings.apply_audio()
    
    # Default to 720p window
    window = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
    pygame.display.set_caption(GAME_TITLE)
    apply_screen_mode(window, settings.screen_mode)
    
    clock = pygame.time.Clock()
    canvas = pygame.Surface((VIRTUAL_W, VIRTUAL_H))
    
    # Fonts
    font_small = pygame.font.SysFont("arial", 12, bold=True)
    font_med = pygame.font.SysFont("arial", 18, bold=True)
    font_big = pygame.font.SysFont("arial", 32, bold=True)

    # === SPRITE LOADING ===
    slime_path = get_asset_path("data", "gfx", "Slimes")
    
    # P1 (Blue - Row index 3)
    p1_idle_main = load_sprite_sheet(os.path.join(slime_path, "slime_idle1.png"), 2, 7, 3)
    p1_idle_alt1 = load_sprite_sheet(os.path.join(slime_path, "slime_idle2.png"), 7, 7, 3)
    p1_idle_alt2 = load_sprite_sheet(os.path.join(slime_path, "slime_idle3.png"), 7, 7, 3)
    p1_jump_frames = load_sprite_sheet(os.path.join(slime_path, "slime_jump.png"), 11, 7, 3)

    p1_sprites = {
        "idle_main": p1_idle_main,
        "idle_alt1": p1_idle_alt1,
        "idle_alt2": p1_idle_alt2,
        "move": load_sprite_sheet(os.path.join(slime_path, "slime_move.png"), 7, 7, 3),
        "jump": p1_jump_frames,
        "fall": p1_jump_frames,
        "slam_frames": p1_jump_frames,
        "hit": load_sprite_sheet(os.path.join(slime_path, "slime_hit.png"), 2, 7, 3),
        "die": load_sprite_sheet(os.path.join(slime_path, "slime_die.png"), 13, 7, 3),
        "swallow": load_sprite_sheet(os.path.join(slime_path, "slime_swallow.png"), 14, 7, 3)
    }

    # P2 (Red - Row index 1)
    p2_idle_main = load_sprite_sheet(os.path.join(slime_path, "slime_idle1.png"), 2, 7, 1)
    p2_idle_alt1 = load_sprite_sheet(os.path.join(slime_path, "slime_idle2.png"), 7, 7, 1)
    p2_idle_alt2 = load_sprite_sheet(os.path.join(slime_path, "slime_idle3.png"), 7, 7, 1)
    p2_jump_frames = load_sprite_sheet(os.path.join(slime_path, "slime_jump.png"), 11, 7, 1)

    p2_sprites = {
        "idle_main": p2_idle_main,
        "idle_alt1": p2_idle_alt1,
        "idle_alt2": p2_idle_alt2,
        "move": load_sprite_sheet(os.path.join(slime_path, "slime_move.png"), 7, 7, 1),
        "jump": p2_jump_frames,
        "fall": p2_jump_frames,
        "slam_frames": p2_jump_frames,
        "hit": load_sprite_sheet(os.path.join(slime_path, "slime_hit.png"), 2, 7, 1),
        "die": load_sprite_sheet(os.path.join(slime_path, "slime_die.png"), 13, 7, 1),
        "swallow": load_sprite_sheet(os.path.join(slime_path, "slime_swallow.png"), 14, 7, 1)
    }

    player1_sprite = p1_sprites
    player2_sprite = p2_sprites
    
    # Enemy sprites
    enemy_path = get_asset_path("data", "gfx", "Enemy")
    ENEMY_SCALE = 0.9
    
    enemy_walk_frames = load_sprite_sheet(os.path.join(enemy_path, "spr_monster_reg_strip4.png"), 4, 1, 0, scale=ENEMY_SCALE)
    enemy_hurt_frames = load_sprite_sheet(os.path.join(enemy_path, "spr_enemy_reg_hurt_strip4.png"), 4, 1, 0, scale=ENEMY_SCALE)

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
    
    # Backgrounds
    day_bg = ParallaxBackground("Day", VIRTUAL_W, VIRTUAL_H)
    night_bg = ParallaxBackground("Night", VIRTUAL_W, VIRTUAL_H)
    menu_scroll_x = 0.0

    MENU_BGM_PATH = get_asset_path("data", "sfx", "pck404_cosy_bossa.ogg")
    
    def play_menu_music():
        if os.path.exists(MENU_BGM_PATH):
            try:
                pygame.mixer.music.load(MENU_BGM_PATH)
                pygame.mixer.music.set_volume(settings.music_volume * settings.master_volume)
                pygame.mixer.music.play(-1)
            except Exception as e:
                print(f"Music load failed: {e}")

    play_menu_music()
    
    def start_game_wrapper(*args, **kwargs):
        start_game(*args, **kwargs)
        play_menu_music()
    
    # UI State
    main_buttons = []
    settings_widgets = []
    shop_buttons = []
    settings_scroll = 0.0
    mp_buttons = []
    mp_mode = MODE_VERSUS
    show_kick_confirm = False
    mp_connection_type = "local"
    
    controls_widgets = []
    controls_scroll = 0.0

    mp_ip_input = TextInput(pygame.Rect(140, 170, 200, 30), font_small, "", "Enter IP Address...")
    
    room_list = {}
    selected_room = None
    
    global_anim_timer = 0.0
    
    # Character Selection State
    char_select_buttons = []
    selected_color_index = 3
    selected_ability_index = 0
    char_preview_sprites = None
    char_preview_time = 0.0
    
    # MP Character Selection State
    mp_char_buttons = []
    p1_color_index = 3
    p1_ability_index = 0
    p2_color_index = 1
    p2_ability_index = 0
    p1_preview_sprites = None
    p2_preview_sprites = None
    mp_char_preview_time = 0.0

    def rebuild_main_menu():
        main_buttons.clear()
        y = 100
        def add_btn(label, cb, color=COL_UI_BG, accent=COL_ACCENT_1):
            nonlocal y
            rect = pygame.Rect(VIRTUAL_W // 2 - 100, y, 200, 40)
            main_buttons.append(Button(rect, label, font_med, cb, color=color, accent=accent))
            y += 50
        
        add_btn("Single Player", lambda: set_state(STATE_CHARACTER_SELECT))
        add_btn("Multiplayer", lambda: set_state(STATE_MP_LOBBY), accent=COL_ACCENT_3)
        add_btn("Shop", lambda: set_state(STATE_SHOP))
        add_btn("Settings", lambda: set_state(STATE_SETTINGS))
        add_btn("Quit", lambda: stop(), color=(40, 10, 10))

    def rebuild_character_select():
        nonlocal char_preview_sprites
        char_select_buttons.clear()
        
        color_row = CHARACTER_COLORS[selected_color_index]["row"]
        char_preview_sprites = load_character_sprites(slime_path, color_row)
        
        def prev_color():
            nonlocal selected_color_index
            selected_color_index = (selected_color_index - 1) % len(CHARACTER_COLORS)
            rebuild_character_select()
        
        def next_color():
            nonlocal selected_color_index
            selected_color_index = (selected_color_index + 1) % len(CHARACTER_COLORS)
            rebuild_character_select()
        
        def prev_ability():
            nonlocal selected_ability_index
            selected_ability_index = (selected_ability_index - 1) % len(CHARACTER_ABILITIES)
        
        def next_ability():
            nonlocal selected_ability_index
            selected_ability_index = (selected_ability_index + 1) % len(CHARACTER_ABILITIES)
        
        def start_with_selection():
            custom_sprites = load_character_sprites(slime_path, CHARACTER_COLORS[selected_color_index]["row"])
            ability_name = CHARACTER_ABILITIES[selected_ability_index]["name"]
            
            start_game_wrapper(settings, window, canvas, font_small, font_med, font_big, 
                             custom_sprites, player2_sprite, enemy_sprite_dict, tile_surf, 
                             wall_surf, lb, network, ROLE_LOCAL_ONLY, MODE_SINGLE, None, 
                             local_two_players=False, bg_obj=night_bg, 
                             p1_ability=ability_name)
        
        char_select_buttons.append(Button(pygame.Rect(180, 220, 40, 35), "<", font_med, prev_color))
        char_select_buttons.append(Button(pygame.Rect(420, 220, 40, 35), ">", font_med, next_color))
        
        char_select_buttons.append(Button(pygame.Rect(180, 290, 40, 35), "<", font_med, prev_ability))
        char_select_buttons.append(Button(pygame.Rect(420, 290, 40, 35), ">", font_med, next_ability))
        
        char_select_buttons.append(Button(pygame.Rect(110, 380, 140, 45), "RETURN", font_med, lambda: set_state(STATE_MAIN_MENU)))
        char_select_buttons.append(Button(pygame.Rect(390, 380, 140, 45), "START", font_med, start_with_selection, accent=COL_ACCENT_3))

    def rebuild_shop_menu():
        shop_buttons.clear()
        shop_buttons.append(Button(pygame.Rect(20, VIRTUAL_H - 50, 80, 30), "Back", font_small, lambda: set_state(STATE_MAIN_MENU)))
        
        y_start = 70
        row_height = 65
        panel_h = 50
        btn_h = 35
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

        add_slider("Master Volume", lambda: settings.master_volume, lambda v: (setattr(settings, "master_volume", v), settings.apply_audio()), 0.0, 1.0)
        add_slider("Music Volume", lambda: settings.music_volume, lambda v: (setattr(settings, "music_volume", v), settings.apply_audio()), 0.0, 1.0)
        add_slider("SFX Volume", lambda: settings.sfx_volume, lambda v: setattr(settings, "sfx_volume", v), 0.0, 1.0)
        add_toggle("Screen Mode", ["Window", "Fullscreen", "Borderless"], lambda: settings.screen_mode, lambda idx: (setattr(settings, "screen_mode", idx), apply_screen_mode(window, idx)))
        
        y += 20 
        
        button_width = 200
        button_height = 45
        
        rect_controls = pygame.Rect(VIRTUAL_W // 2 - button_width // 2, y, button_width, button_height)
        settings_widgets.append(Button(rect_controls, "Change keybinds", font_med, lambda: set_state(STATE_CONTROLS), accent=COL_ACCENT_3))
        
        y += button_height + 20

        rect_return = pygame.Rect(VIRTUAL_W // 2 - button_width // 2, y, button_width, button_height)
        settings_widgets.append(Button(rect_return, "Return to Main Menu", font_med, lambda: set_state(STATE_MAIN_MENU)))

    def rebuild_controls_menu():
        nonlocal controls_scroll
        controls_widgets.clear()
        controls_scroll = 0.0
        
        y = 80
        
        def make_update_callback(action_key):
            def callback(new_code):
                settings.keybinds[action_key] = new_code
            return callback
        
        p1_x = 30
        p1_width = 280
        p1_button_height = 40
        p1_spacing = 12
        
        controls_widgets.append(SectionHeader(p1_x + p1_width // 2, y, "PLAYER 1", font_med, COL_ACCENT_1))
        p1_y = y + 40
        
        p1_actions = [("p1_left", "Left"), ("p1_right", "Right"), ("p1_jump", "Jump"), ("p1_slam", "Ability")]
        for key, name in p1_actions:
            default_kb = DEFAULT_KEYBINDS if DEFAULT_KEYBINDS else init_default_keybinds()
            current_code = settings.keybinds.get(key, default_kb[key])
            rect = pygame.Rect(p1_x, p1_y, p1_width, p1_button_height)
            btn = KeybindButton(rect, name, current_code, font_small, make_update_callback(key))
            controls_widgets.append(btn)
            p1_y += p1_button_height + p1_spacing
        
        p2_x = VIRTUAL_W - p1_width - 30
        p2_width = 280
        p2_button_height = 40
        p2_spacing = 12
        
        controls_widgets.append(SectionHeader(p2_x + p2_width // 2, y, "PLAYER 2", font_med, COL_ACCENT_2))
        p2_y = y + 40
        
        p2_actions = [("p2_left", "Left"), ("p2_right", "Right"), ("p2_jump", "Jump"), ("p2_slam", "Ability")]
        for key, name in p2_actions:
            default_kb = DEFAULT_KEYBINDS if DEFAULT_KEYBINDS else init_default_keybinds()
            current_code = settings.keybinds.get(key, default_kb[key])
            rect = pygame.Rect(p2_x, p2_y, p2_width, p2_button_height)
            btn = KeybindButton(rect, name, current_code, font_small, make_update_callback(key))
            controls_widgets.append(btn)
            p2_y += p2_button_height + p2_spacing
        
        y = max(p1_y, p2_y) + 30
        
        def reset_defaults():
            default_kb = DEFAULT_KEYBINDS if DEFAULT_KEYBINDS else init_default_keybinds()
            settings.keybinds = default_kb.copy()
            rebuild_controls_menu()
        
        button_width = 180
        button_height = 40
        rect_reset = pygame.Rect(VIRTUAL_W // 2 - button_width // 2, y, button_width, button_height)
        controls_widgets.append(Button(rect_reset, "RESET DEFAULTS", font_med, reset_defaults, accent=(255, 80, 80)))
        
        y += button_height + 20
        
        rect_back = pygame.Rect(VIRTUAL_W // 2 - button_width // 2, y, button_width, button_height)
        controls_widgets.append(Button(rect_back, "Back to Settings", font_med, lambda: set_state(STATE_SETTINGS)))

    def rebuild_mp_lobby():
        mp_buttons.clear()
        
        y = 150
        mp_buttons.append(Button(pygame.Rect(VIRTUAL_W // 2 - 100, y, 200, 50), "Create Room", font_med, 
                                 lambda: set_state(STATE_MP_MODE), accent=COL_ACCENT_3))
        y += 70
        mp_buttons.append(Button(pygame.Rect(VIRTUAL_W // 2 - 100, y, 200, 50), "Join Room", font_med, 
                                 lambda: set_state(STATE_MP_ROOM_BROWSER)))
        
        mp_buttons.append(Button(pygame.Rect(20, VIRTUAL_H - 50, 80, 30), "Return", font_small, 
                                 lambda: set_state(STATE_MAIN_MENU)))
    
    def rebuild_mp_mode():
        mp_buttons.clear()
        
        y = 150
        def choose_local():
            nonlocal mp_connection_type
            mp_connection_type = "local"
            set_state(STATE_MP_CHARACTER_SELECT)
        
        mp_buttons.append(Button(pygame.Rect(VIRTUAL_W // 2 - 100, y, 200, 50), "LOCAL", font_med, 
                                 choose_local, accent=COL_ACCENT_1))
        y += 70
        
        def choose_lan():
            nonlocal mp_connection_type, p1_color_index, p2_color_index, p1_ability_index, p2_ability_index
            mp_connection_type = "lan"
            p1_color_index = 3
            p2_color_index = 1
            p1_ability_index = 0
            p2_ability_index = 0
            network.host()
            set_state(STATE_MP_CHARACTER_SELECT)
        
        mp_buttons.append(Button(pygame.Rect(VIRTUAL_W // 2 - 100, y, 200, 50), "LAN", font_med, 
                                 choose_lan, accent=COL_ACCENT_3))
        
        mp_buttons.append(Button(pygame.Rect(20, VIRTUAL_H - 50, 80, 30), "Return", font_small, 
                                 lambda: set_state(STATE_MP_LOBBY)))
    
    def rebuild_mp_character_select():
        nonlocal p1_preview_sprites, p2_preview_sprites
        mp_char_buttons.clear()
        
        p1_preview_sprites = load_character_sprites(slime_path, CHARACTER_COLORS[p1_color_index]["row"])
        p2_preview_sprites = load_character_sprites(slime_path, CHARACTER_COLORS[p2_color_index]["row"])
        
        def p1_prev_color():
            nonlocal p1_color_index
            p1_color_index = (p1_color_index - 1) % len(CHARACTER_COLORS)
            if mp_connection_type == "lan" and network.role == ROLE_HOST:
                network.send_char_selection(p1_color_index, p1_ability_index)
            rebuild_mp_character_select()
        
        def p1_next_color():
            nonlocal p1_color_index
            p1_color_index = (p1_color_index + 1) % len(CHARACTER_COLORS)
            if mp_connection_type == "lan" and network.role == ROLE_HOST:
                network.send_char_selection(p1_color_index, p1_ability_index)
            rebuild_mp_character_select()
        
        def p1_prev_ability():
            nonlocal p1_ability_index
            p1_ability_index = (p1_ability_index - 1) % len(CHARACTER_ABILITIES)
            if mp_connection_type == "lan" and network.role == ROLE_HOST:
                network.send_char_selection(p1_color_index, p1_ability_index)
        
        def p1_next_ability():
            nonlocal p1_ability_index
            p1_ability_index = (p1_ability_index + 1) % len(CHARACTER_ABILITIES)
            if mp_connection_type == "lan" and network.role == ROLE_HOST:
                network.send_char_selection(p1_color_index, p1_ability_index)
        
        def p2_prev_color():
            nonlocal p2_color_index
            p2_color_index = (p2_color_index - 1) % len(CHARACTER_COLORS)
            if mp_connection_type == "lan" and network.role == ROLE_CLIENT:
                network.send_char_selection(p2_color_index, p2_ability_index)
            rebuild_mp_character_select()
        
        def p2_next_color():
            nonlocal p2_color_index
            p2_color_index = (p2_color_index + 1) % len(CHARACTER_COLORS)
            if mp_connection_type == "lan" and network.role == ROLE_CLIENT:
                network.send_char_selection(p2_color_index, p2_ability_index)
            rebuild_mp_character_select()
        
        def p2_prev_ability():
            nonlocal p2_ability_index
            p2_ability_index = (p2_ability_index - 1) % len(CHARACTER_ABILITIES)
            if mp_connection_type == "lan" and network.role == ROLE_CLIENT:
                network.send_char_selection(p2_color_index, p2_ability_index)
        
        def p2_next_ability():
            nonlocal p2_ability_index
            p2_ability_index = (p2_ability_index + 1) % len(CHARACTER_ABILITIES)
            if mp_connection_type == "lan" and network.role == ROLE_CLIENT:
                network.send_char_selection(p2_color_index, p2_ability_index)
        
        p1_x = 210
        p1_color_left = Button(pygame.Rect(p1_x - 70, 220, 40, 35), "<", font_med, p1_prev_color)
        p1_color_right = Button(pygame.Rect(p1_x + 30, 220, 40, 35), ">", font_med, p1_next_color)
        p1_ability_left = Button(pygame.Rect(p1_x - 70, 290, 40, 35), "<", font_med, p1_prev_ability)
        p1_ability_right = Button(pygame.Rect(p1_x + 30, 290, 40, 35), ">", font_med, p1_next_ability)
        
        if network.role == ROLE_CLIENT:
            p1_color_left.disabled = True
            p1_color_right.disabled = True
            p1_ability_left.disabled = True
            p1_ability_right.disabled = True
        
        mp_char_buttons.extend([p1_color_left, p1_color_right, p1_ability_left, p1_ability_right])
        
        p2_x = 430
        p2_color_left = Button(pygame.Rect(p2_x - 70, 220, 40, 35), "<", font_med, p2_prev_color)
        p2_color_right = Button(pygame.Rect(p2_x + 30, 220, 40, 35), ">", font_med, p2_next_color)
        p2_ability_left = Button(pygame.Rect(p2_x - 70, 290, 40, 35), "<", font_med, p2_prev_ability)
        p2_ability_right = Button(pygame.Rect(p2_x + 30, 290, 40, 35), ">", font_med, p2_next_ability)
        
        if mp_connection_type == "lan" and network.role == ROLE_HOST:
            p2_color_left.disabled = True
            p2_color_right.disabled = True
            p2_ability_left.disabled = True
            p2_ability_right.disabled = True
        
        mp_char_buttons.extend([p2_color_left, p2_color_right, p2_ability_left, p2_ability_right])
        
        def start_mp_game():
            p1_sprites_game = load_character_sprites(slime_path, CHARACTER_COLORS[p1_color_index]["row"])
            p2_sprites_game = load_character_sprites(slime_path, CHARACTER_COLORS[p2_color_index]["row"])
            
            p1_ab = CHARACTER_ABILITIES[p1_ability_index]["name"]
            p2_ab = CHARACTER_ABILITIES[p2_ability_index]["name"]
            
            if mp_connection_type == "local":
                start_game_wrapper(settings, window, canvas, font_small, font_med, font_big, 
                                 p1_sprites_game, p2_sprites_game, enemy_sprite_dict, tile_surf, 
                                 wall_surf, lb, network, ROLE_LOCAL_ONLY, mp_mode, None, 
                                 local_two_players=True, bg_obj=night_bg,
                                 p1_ability=p1_ab, p2_ability=p2_ab)
            else:
                if network.connected:
                    network.send_start_game()
                    time.sleep(0.2)
                start_game_wrapper(settings, window, canvas, font_small, font_med, font_big, 
                                 p1_sprites_game, p2_sprites_game, enemy_sprite_dict, tile_surf, 
                                 wall_surf, lb, network, network.role, mp_mode, None, 
                                 local_two_players=False, bg_obj=night_bg,
                                 p1_ability=p1_ab, p2_ability=p2_ab)
        
        def return_action():
            if mp_connection_type == "lan":
                if network.role == ROLE_HOST:
                    if network.connected:
                        network.send_kick()
                        time.sleep(0.1)
                network.close()
            if network.role == ROLE_CLIENT:
                set_state(STATE_MP_ROOM_BROWSER)
            else:
                set_state(STATE_MP_MODE)
        
        if mp_connection_type == "lan" and network.role == ROLE_HOST:
            button_text = "DISBAND"
        elif mp_connection_type == "lan" and network.role == ROLE_CLIENT:
            button_text = "LEAVE ROOM"
        else:
            button_text = "RETURN"
        
        mp_char_buttons.append(Button(pygame.Rect(80, 380, 140, 45), button_text, font_med, return_action))
        
        if network.role != ROLE_CLIENT:
            def toggle_mp_mode():
                nonlocal mp_mode
                mp_mode = MODE_COOP if mp_mode == MODE_VERSUS else MODE_VERSUS
                if network.role == ROLE_HOST:
                    network.scanner.broadcast_mode = mp_mode
                rebuild_mp_character_select()
            
            mode_text = f"Mode: {'Co-op' if mp_mode == MODE_COOP else 'Versus'}"
            mp_char_buttons.append(Button(pygame.Rect(250, 380, 140, 45), mode_text, font_med, toggle_mp_mode))
        else:
            mode_text = f"Mode: {'Co-op' if mp_mode == MODE_COOP else 'Versus'}"
            mode_label = Button(pygame.Rect(250, 380, 140, 45), mode_text, font_med, lambda: None)
            mode_label.disabled = True
            mp_char_buttons.append(mode_label)
        
        if network.role != ROLE_CLIENT:
            mp_char_buttons.append(Button(pygame.Rect(420, 380, 140, 45), "START", font_med, 
                                          start_mp_game, accent=COL_ACCENT_3))
        else:
            waiting_label = Button(pygame.Rect(420, 380, 140, 45), "Waiting...", font_med, lambda: None)
            waiting_label.disabled = True
            mp_char_buttons.append(waiting_label)
    
    def rebuild_mp_room_browser():
        mp_buttons.clear()
        
        def refresh_action():
            nonlocal selected_room
            network.scanner.found_hosts = {}
            nonlocal room_list
            room_list = {}
            selected_room = None
        
        mp_buttons.append(Button(pygame.Rect(80, VIRTUAL_H - 70, 140, 40), 
                                 "Return", font_med, lambda: (network.close(), set_state(STATE_MP_LOBBY))))
        
        mp_buttons.append(Button(pygame.Rect(VIRTUAL_W // 2 - 70, VIRTUAL_H - 70, 140, 40), 
                                 "Refresh", font_med, refresh_action))
        
        def join_room_action():
            nonlocal mp_connection_type, mp_mode, p1_color_index, p2_color_index, p1_ability_index, p2_ability_index
            if selected_room:
                if selected_room in room_list:
                    mp_mode = room_list[selected_room]
                network.join(selected_room)
                mp_connection_type = "lan"
                p1_color_index = 3
                p2_color_index = 1
                p1_ability_index = 0
                p2_ability_index = 0
                set_state(STATE_MP_CHARACTER_SELECT)
        
        join_btn = Button(pygame.Rect(VIRTUAL_W - 220, VIRTUAL_H - 70, 140, 40), 
                          "Join Room", font_med, join_room_action, accent=COL_ACCENT_3)
        
        if not selected_room:
            join_btn.disabled = True
        
        mp_buttons.append(join_btn)
    
    def rebuild_mp_menu():
        rebuild_mp_lobby()

    def set_state(s):
        nonlocal game_state
        save_data.update(load_save_data())
        
        game_state = s
        if s == STATE_MAIN_MENU: rebuild_main_menu()
        elif s == STATE_SETTINGS: rebuild_settings_menu()
        elif s == STATE_CONTROLS: rebuild_controls_menu()
        elif s == STATE_SHOP: rebuild_shop_menu()
        elif s == STATE_CHARACTER_SELECT: rebuild_character_select()
        elif s == STATE_MULTIPLAYER_MENU: 
            network.scanner.found_hosts = []
            rebuild_mp_menu()
        elif s == STATE_MP_LOBBY: rebuild_mp_lobby()
        elif s == STATE_MP_MODE: rebuild_mp_mode()
        elif s == STATE_MP_CHARACTER_SELECT: rebuild_mp_character_select()
        elif s == STATE_MP_ROOM_BROWSER: 
            network.scanner.found_hosts = []
            rebuild_mp_room_browser()
    
    def stop(): 
        nonlocal running
        running = False

    rebuild_main_menu()
    rebuild_settings_menu()
    rebuild_controls_menu()
    rebuild_mp_menu()
    
    host_sync_timer = 0.0
    last_connected_status = False

    # ========== MAIN MENU LOOP ==========
    while running:
        dt = clock.tick(settings.target_fps) / 1000.0
        dt = min(dt, 0.05)
        global_anim_timer += dt

        if game_state in (STATE_MAIN_MENU, STATE_SETTINGS, STATE_CONTROLS, STATE_SHOP, STATE_MULTIPLAYER_MENU, STATE_LEADERBOARD, 
                          STATE_CHARACTER_SELECT, STATE_MP_LOBBY, STATE_MP_MODE, STATE_MP_CHARACTER_SELECT, STATE_MP_ROOM_BROWSER):
            if not pygame.mixer.music.get_busy():
                play_menu_music()
        
        if game_state == STATE_CHARACTER_SELECT:
            char_preview_time += dt
        
        if game_state == STATE_MP_CHARACTER_SELECT:
            mp_char_preview_time += dt
        
        win_w, win_h = window.get_size()
        scale = min(win_w / VIRTUAL_W, win_h / VIRTUAL_H)
        scaled_w, scaled_h = int(VIRTUAL_W * scale), int(VIRTUAL_H * scale)
        offset_x, offset_y = (win_w - scaled_w) // 2, (win_h - scaled_h) // 2

        if game_state == STATE_MP_ROOM_BROWSER:
            network.scanner.listen()
            current_hosts = network.scanner.found_hosts
            room_list = dict(current_hosts)
        
        if game_state == STATE_MP_CHARACTER_SELECT and mp_connection_type == "lan":
            if network.role == ROLE_HOST:
                host_sync_timer += dt
                if host_sync_timer > 0.5: 
                    network.send_lobby_mode(mp_mode)
                    network.scanner.broadcast(mp_mode)
                    host_sync_timer = 0
                
                network.poll_remote_state()
                remote_color, remote_ability = network.get_remote_char_selection()
                if remote_color != p2_color_index or remote_ability != p2_ability_index:
                    p2_color_index = remote_color
                    p2_ability_index = remote_ability
                    rebuild_mp_character_select()
            elif network.role == ROLE_CLIENT:
                network.poll_remote_state()
                
                if not network.connected:
                    set_state(STATE_MP_ROOM_BROWSER)
                    continue
                
                remote_color, remote_ability = network.get_remote_char_selection()
                if remote_color != p1_color_index or remote_ability != p1_ability_index:
                    p1_color_index = remote_color
                    p1_ability_index = remote_ability
                    rebuild_mp_character_select()
                
                remote_mode = network.get_remote_lobby_mode()
                if remote_mode and remote_mode != mp_mode:
                    mp_mode = remote_mode
                    rebuild_mp_character_select()
                if network.check_remote_start():
                    p1_sprites_game = load_character_sprites(slime_path, CHARACTER_COLORS[p1_color_index]["row"])
                    p2_sprites_game = load_character_sprites(slime_path, CHARACTER_COLORS[p2_color_index]["row"])
                    p1_ab = CHARACTER_ABILITIES[p1_ability_index]["name"]
                    p2_ab = CHARACTER_ABILITIES[p2_ability_index]["name"]
                    start_game_wrapper(settings, window, canvas, font_small, font_med, font_big, 
                                     p1_sprites_game, p2_sprites_game, enemy_sprite_dict, tile_surf, 
                                     wall_surf, lb, network, network.role, mp_mode, None, 
                                     local_two_players=False, bg_obj=night_bg,
                                     p1_ability=p1_ab, p2_ability=p2_ab)
        
        if game_state == STATE_MULTIPLAYER_MENU:
            network.scanner.listen()
            current_hosts = network.scanner.found_hosts
            if set(current_hosts) != set(room_list): room_list = list(current_hosts)
            if network.sock: network.poll_remote_state()
            if network.connected != last_connected_status:
                last_connected_status = network.connected
                rebuild_mp_menu()
            if network.role == ROLE_CLIENT and network.check_remote_start():
                start_game_wrapper(settings, window, canvas, font_small, font_med, font_big, player1_sprite, player2_sprite, enemy_sprite_dict, tile_surf, wall_surf, lb, network, network.role, mp_mode, mp_ip_input.text, network.role == ROLE_LOCAL_ONLY, bg_obj=night_bg)
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

        # Event Handling
        for raw_event in pygame.event.get():
            if raw_event.type == pygame.QUIT: 
                if network.connected:
                    try:
                        network.send_lobby_exit()
                        network.sock.close()
                    except: pass
                running = False
            elif raw_event.type == pygame.VIDEORESIZE:
                window = pygame.display.set_mode(raw_event.size, pygame.RESIZABLE)
            
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
            elif game_state == STATE_CHARACTER_SELECT:
                for b in char_select_buttons: b.handle_event(ui_event)
                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE: set_state(STATE_MAIN_MENU)
            elif game_state == STATE_SHOP:
                for b in shop_buttons: b.handle_event(ui_event)
                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE: set_state(STATE_MAIN_MENU)
            elif game_state == STATE_SETTINGS:
                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE: 
                    settings.save()
                    set_state(STATE_MAIN_MENU)
                if raw_event.type == pygame.MOUSEWHEEL: settings_scroll -= raw_event.y * 20
                sevt = ui_event
                if ui_event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and "pos" in ui_event.dict:
                    sevt = pygame.event.Event(ui_event.type, {**ui_event.dict, "pos": (ui_event.pos[0], ui_event.pos[1] + settings_scroll)})
                for w in settings_widgets: w.handle_event(sevt)
            elif game_state == STATE_CONTROLS:
                if raw_event.type == pygame.MOUSEWHEEL: controls_scroll -= raw_event.y * 20
                
                sevt = ui_event
                if ui_event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and "pos" in ui_event.dict:
                    sevt = pygame.event.Event(ui_event.type, {**ui_event.dict, "pos": (ui_event.pos[0], ui_event.pos[1] + controls_scroll)})
                
                any_listening = any(getattr(w, 'listening', False) for w in controls_widgets if hasattr(w, 'listening'))
                
                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE:
                    if not any_listening:
                        settings.save()
                        set_state(STATE_SETTINGS)
                
                for w in controls_widgets: w.handle_event(sevt)
            elif game_state == STATE_MP_LOBBY:
                for b in mp_buttons: b.handle_event(ui_event)
                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE: set_state(STATE_MAIN_MENU)
            elif game_state == STATE_MP_MODE:
                for b in mp_buttons: b.handle_event(ui_event)
                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE: set_state(STATE_MP_LOBBY)
            elif game_state == STATE_MP_CHARACTER_SELECT:
                for b in mp_char_buttons: b.handle_event(ui_event)
            elif game_state == STATE_MP_ROOM_BROWSER:
                for b in mp_buttons: b.handle_event(ui_event)
                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE: 
                    network.close()
                    set_state(STATE_MP_LOBBY)
                if raw_event.type == pygame.MOUSEBUTTONDOWN:
                    y_offset = 80
                    for i, (room_ip, room_mode) in enumerate(list(room_list.items())[:6]):
                        room_rect = pygame.Rect(60, y_offset, VIRTUAL_W - 120, 35)
                        if ui_event.type == pygame.MOUSEBUTTONDOWN:
                            mx, my = ui_event.pos
                            if room_rect.collidepoint(mx, my):
                                selected_room = room_ip
                                rebuild_mp_room_browser()
                                break
                        y_offset += 40

        # Rendering
        canvas.fill(COL_BG)

        if game_state == STATE_MAIN_MENU:
            menu_scroll_x += dt * 60
            day_bg.draw(canvas, menu_scroll_x)
            draw_text_shadow(canvas, font_big, GAME_TITLE, VIRTUAL_W//2, 50, center=True, pulse=True, time_val=global_anim_timer)
            for b in main_buttons: b.draw(canvas, dt)
            draw_text_shadow(canvas, font_small, f"Credits: {save_data['credits']}", VIRTUAL_W - 100, 15)

        elif game_state == STATE_CHARACTER_SELECT:
            menu_scroll_x += dt * 60
            day_bg.draw(canvas, menu_scroll_x)
            draw_text_shadow(canvas, font_big, "Character Select", VIRTUAL_W//2, 40, center=True)
            
            center_x = VIRTUAL_W // 2
            center_y = 140
            pygame.draw.circle(canvas, COL_UI_BG, (center_x, center_y), 50)
            pygame.draw.circle(canvas, COL_ACCENT_1, (center_x, center_y), 50, 3)
            if char_preview_sprites:
                draw_character_preview(canvas, char_preview_sprites, char_preview_time, center_x, center_y)
            
            color_name = CHARACTER_COLORS[selected_color_index]["name"]
            ability_name = CHARACTER_ABILITIES[selected_ability_index]["name"]
            ability_desc = CHARACTER_ABILITIES[selected_ability_index]["description"]
            
            draw_text_shadow(canvas, font_med, f"{color_name}", center_x, 237, center=True, col=COL_ACCENT_1)
            draw_text_shadow(canvas, font_med, f"{ability_name}", center_x, 307, center=True, col=COL_ACCENT_3)
            draw_text_shadow(canvas, font_small, ability_desc, center_x, 345, center=True, col=(180, 180, 180))
            
            for b in char_select_buttons: b.draw(canvas, dt)

        elif game_state == STATE_SHOP:
            draw_text_shadow(canvas, font_big, "Upgrade Shop", 20, 20)
            draw_text_shadow(canvas, font_small, f"Credits: {save_data['credits']}", VIRTUAL_W - 100, 15, col=COL_ACCENT_3)
            
            y_start = 70
            row_height = 65
            panel_h = 50
            
            for i, (key, info) in enumerate(UPGRADE_INFO.items()):
                row_y = y_start + i * row_height
                draw_panel(canvas, pygame.Rect(20, row_y, VIRTUAL_W - 40, panel_h))
                
                lvl = save_data["upgrades"].get(key, 0)
                draw_text_shadow(canvas, font_med, info["name"], 30, row_y + 8)
                draw_text_shadow(canvas, font_small, info["desc"], 30, row_y + 28, col=(150, 150, 150))
                
                level_text = f"Lv {lvl}/{info['max']}"
                draw_text_shadow(canvas, font_small, level_text, VIRTUAL_W - 200, row_y + 18, col=COL_ACCENT_1)
            
            for b in shop_buttons: b.draw(canvas, dt)

        elif game_state == STATE_SETTINGS:
            draw_text_shadow(canvas, font_big, "Settings", VIRTUAL_W // 2, 30, center=True)
            
            for w in settings_widgets:
                orig_y = w.rect.y
                w.rect.y = orig_y - settings_scroll
                
                if w.rect.bottom > 0 and w.rect.top < VIRTUAL_H: 
                     w.draw(canvas)
                
                w.rect.y = orig_y

        elif game_state == STATE_CONTROLS:
            draw_text_shadow(canvas, font_big, "Controls", VIRTUAL_W // 2, 30, center=True)
            
            for w in controls_widgets:
                orig_y = w.rect.y if hasattr(w, 'rect') else 0
                if hasattr(w, 'rect'):
                    w.rect.y = orig_y - controls_scroll
                
                if hasattr(w, 'rect') and w.rect.bottom > 0 and w.rect.top < VIRTUAL_H: 
                     w.draw(canvas)
                elif not hasattr(w, 'rect'):
                    w.draw(canvas)
                
                if hasattr(w, 'rect'):
                    w.rect.y = orig_y

        elif game_state == STATE_MP_LOBBY:
            menu_scroll_x += dt * 60
            day_bg.draw(canvas, menu_scroll_x)
            draw_text_shadow(canvas, font_big, "Multiplayer", VIRTUAL_W//2, 60, center=True, pulse=True, time_val=global_anim_timer)
            for b in mp_buttons: b.draw(canvas, dt)
        
        elif game_state == STATE_MP_MODE:
            menu_scroll_x += dt * 60
            day_bg.draw(canvas, menu_scroll_x)
            draw_text_shadow(canvas, font_big, "Choose Mode", VIRTUAL_W//2, 60, center=True)
            for b in mp_buttons: b.draw(canvas, dt)
        
        elif game_state == STATE_MP_CHARACTER_SELECT:
            menu_scroll_x += dt * 60
            day_bg.draw(canvas, menu_scroll_x)
            draw_text_shadow(canvas, font_big, "Character Select", VIRTUAL_W//2, 40, center=True)
            
            p1_center_x = 210
            p1_center_y = 140
            pygame.draw.circle(canvas, COL_UI_BG, (p1_center_x, p1_center_y), 50)
            pygame.draw.circle(canvas, COL_ACCENT_1, (p1_center_x, p1_center_y), 50, 3)
            if p1_preview_sprites:
                draw_character_preview(canvas, p1_preview_sprites, mp_char_preview_time, p1_center_x, p1_center_y)
            draw_text_shadow(canvas, font_small, "P1", p1_center_x, 90, center=True, col=COL_ACCENT_1)
            
            p1_color = CHARACTER_COLORS[p1_color_index]["name"]
            p1_ability = CHARACTER_ABILITIES[p1_ability_index]["name"]
            draw_text_shadow(canvas, font_med, f"{p1_color}", p1_center_x, 237, center=True, col=COL_ACCENT_1)
            draw_text_shadow(canvas, font_med, f"{p1_ability}", p1_center_x, 307, center=True, col=COL_ACCENT_1)
            
            p2_center_x = 430
            p2_center_y = 140
            
            show_p2 = (mp_connection_type == "local") or (mp_connection_type == "lan" and network.connected)
            
            if show_p2:
                pygame.draw.circle(canvas, COL_UI_BG, (p2_center_x, p2_center_y), 50)
                pygame.draw.circle(canvas, COL_ACCENT_2, (p2_center_x, p2_center_y), 50, 3)
                if p2_preview_sprites:
                    draw_character_preview(canvas, p2_preview_sprites, mp_char_preview_time, p2_center_x, p2_center_y)
                draw_text_shadow(canvas, font_small, "P2", p2_center_x, 90, center=True, col=COL_ACCENT_2)
                
                p2_color = CHARACTER_COLORS[p2_color_index]["name"]
                p2_ability = CHARACTER_ABILITIES[p2_ability_index]["name"]
                draw_text_shadow(canvas, font_med, f"{p2_color}", p2_center_x, 237, center=True, col=COL_ACCENT_2)
                draw_text_shadow(canvas, font_med, f"{p2_ability}", p2_center_x, 307, center=True, col=COL_ACCENT_2)
            else:
                pygame.draw.circle(canvas, (30, 30, 40), (p2_center_x, p2_center_y), 50)
                pygame.draw.circle(canvas, (80, 80, 90), (p2_center_x, p2_center_y), 50, 3)
                draw_text_shadow(canvas, font_small, "P2", p2_center_x, 90, center=True, col=(100, 100, 110))
                draw_text_shadow(canvas, font_small, "Waiting for player...", p2_center_x, p2_center_y, center=True, col=(150, 150, 160))
                draw_text_shadow(canvas, font_med, "---", p2_center_x, 237, center=True, col=(80, 80, 90))
                draw_text_shadow(canvas, font_med, "---", p2_center_x, 307, center=True, col=(80, 80, 90))
            
            for b in mp_char_buttons: b.draw(canvas, dt)
        
        elif game_state == STATE_MP_ROOM_BROWSER:
            menu_scroll_x += dt * 60
            day_bg.draw(canvas, menu_scroll_x)
            draw_text_shadow(canvas, font_big, "Server List", VIRTUAL_W//2, 30, center=True)
            
            list_rect = pygame.Rect(50, 70, VIRTUAL_W - 100, 250)
            draw_panel(canvas, list_rect)
            
            if room_list:
                y_offset = 80
                for i, (room_ip, room_mode) in enumerate(list(room_list.items())[:6]):
                    room_rect = pygame.Rect(60, y_offset, VIRTUAL_W - 120, 35)
                    is_selected = (selected_room == room_ip)
                    
                    if is_selected:
                        pygame.draw.rect(canvas, (40, 40, 60), room_rect, border_radius=3)
                    
                    draw_text_shadow(canvas, font_small, f"{room_ip}", 70, y_offset + 8, col=COL_ACCENT_3 if is_selected else COL_TEXT)
                    mode_text = "Co-op" if room_mode == MODE_COOP else "Versus"
                    draw_text_shadow(canvas, font_small, f"Mode: {mode_text}", VIRTUAL_W - 180, y_offset + 8, col=COL_ACCENT_1)
                    
                    y_offset += 40
            else:
                draw_text_shadow(canvas, font_med, "No servers found", VIRTUAL_W//2, 180, center=True, col=(100, 100, 110))
                draw_text_shadow(canvas, font_small, "Click Refresh to scan", VIRTUAL_W//2, 210, center=True, col=(80, 80, 90))
            
            for b in mp_buttons: b.draw(canvas, dt)

        # Scale and Draw to Window
        window.fill((0, 0, 0))
        scaled_surf = pygame.transform.scale(canvas, (scaled_w, scaled_h))
        window.blit(scaled_surf, (offset_x, offset_y))
        pygame.display.flip()

    network.close()
    pygame.quit()
