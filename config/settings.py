"""
Settings class for managing game configuration.
"""
import os
import json
import pygame

from .constants import (
    MODE_WINDOW, START_FPS, SETTINGS_FILE, DEFAULT_KEYBINDS,
    init_default_keybinds
)
from core.data_persistence import ensure_save_dir


class Settings:
    def __init__(self):
        self.master_volume = 0.6
        self.music_volume = 0.5
        self.sfx_volume = 0.8
        self.target_fps = START_FPS
        self.screen_mode = MODE_WINDOW
        # Initialize keybinds
        keybinds = DEFAULT_KEYBINDS
        if keybinds is None:
            keybinds = init_default_keybinds()
        self.keybinds = keybinds.copy()
        self.load()  # Load settings on initialization

    def apply_audio(self):
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(self.music_volume * self.master_volume)
            
    def save(self):
        ensure_save_dir()
        data = {
            "master_volume": self.master_volume,
            "music_volume": self.music_volume,
            "sfx_volume": self.sfx_volume,
            "screen_mode": self.screen_mode,
            "keybinds": self.keybinds
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
                    # Load keybinds, falling back to default if missing
                    saved_keys = data.get("keybinds", {})
                    for k, v in saved_keys.items():
                        if k in self.keybinds:
                            self.keybinds[k] = v
            except Exception as e:
                print(f"Error loading settings: {e}")
