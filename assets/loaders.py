"""
Asset loading functions for sprites, tiles, and boss graphics.
"""
import os
import pygame

from config.constants import get_asset_path, TILE_SIZE, COL_ACCENT_1


def load_sprite_sheet(path, cols, rows, row_index, scale=1.5):
    """
    Extracts frames from a specific row in a sprite sheet.
    """
    frames = []
    if not os.path.exists(path):
        # Fallback: create a placeholder frame
        size = 32  # Default size for a missing slime sprite
        print(f"Warning: Sprite sheet not found: {path}")
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        s.fill((255, 0, 255))  # Hot pink placeholder
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
    pygame.draw.rect(surf, COL_ACCENT_1, (0, 0, TILE_SIZE, 2))  # Neon Top
    pygame.draw.rect(surf, (50, 50, 70), (2, 2, TILE_SIZE-4, TILE_SIZE-4))
    return surf


def make_enemy_surface():
    s = TILE_SIZE * 2
    surf = pygame.Surface((s, s), pygame.SRCALPHA)
    return surf


def make_wall_surface(h):
    surf = pygame.Surface((8, h), pygame.SRCALPHA)
    return surf


def load_boss_sprites():
    """Load Necromancer boss sprite sheets"""
    boss_path = get_asset_path("data", "gfx", "NecromancerBoss", "Necromancer_creativekind-Sheet.png")
    
    if not os.path.exists(boss_path):
        print(f"Warning: Boss sprite sheet not found at {boss_path}")
        # Return placeholder sprites
        placeholder = pygame.Surface((160, 128), pygame.SRCALPHA)
        placeholder.fill((150, 0, 200))
        return {
            "idle": [placeholder],
            "run": [placeholder],
            "attack1": [placeholder],
            "attack2": [placeholder],
            "cast": [placeholder],
            "hit": [placeholder],
            "death": [placeholder]
        }
    
    try:
        sheet = pygame.image.load(boss_path).convert_alpha()
        
        # Frame dimensions based on test.py
        frame_w, frame_h = 160, 128
        scale = 1.5
        
        # Animation definitions (row, frame_count)
        animations = {
            "idle": (0, 8),
            "run": (1, 8),
            "attack1": (2, 13),
            "attack2": (3, 13),
            "cast": (4, 17),
            "hit": (5, 5),
            "death": (6, 10)
        }
        
        sprites = {}
        for anim_name, (row, frame_count) in animations.items():
            frames = []
            for col in range(frame_count):
                rect = pygame.Rect(col * frame_w, row * frame_h, frame_w, frame_h)
                frame = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
                frame.blit(sheet, (0, 0), rect)
                
                # Scale
                scaled_w = int(frame_w * scale)
                scaled_h = int(frame_h * scale)
                frame = pygame.transform.scale(frame, (scaled_w, scaled_h))
                frames.append(frame)
                
            sprites[anim_name] = frames
            
        return sprites
        
    except Exception as e:
        print(f"Error loading boss sprites: {e}")
        placeholder = pygame.Surface((160, 128), pygame.SRCALPHA)
        placeholder.fill((150, 0, 200))
        return {"idle": [placeholder]}


def load_character_sprites(slime_path, color_row):
    """Load all sprite animations for a specific color row."""
    idle_main = load_sprite_sheet(os.path.join(slime_path, "slime_idle1.png"), 2, 7, color_row)
    idle_alt1 = load_sprite_sheet(os.path.join(slime_path, "slime_idle2.png"), 7, 7, color_row)
    idle_alt2 = load_sprite_sheet(os.path.join(slime_path, "slime_idle3.png"), 7, 7, color_row)
    jump_frames = load_sprite_sheet(os.path.join(slime_path, "slime_jump.png"), 11, 7, color_row)

    return {
        "idle_main": idle_main,
        "idle_alt1": idle_alt1,
        "idle_alt2": idle_alt2,
        "move": load_sprite_sheet(os.path.join(slime_path, "slime_move.png"), 7, 7, color_row),
        "jump": jump_frames,
        "fall": jump_frames,
        "slam_frames": jump_frames,
        "hit": load_sprite_sheet(os.path.join(slime_path, "slime_hit.png"), 2, 7, color_row),
        "die": load_sprite_sheet(os.path.join(slime_path, "slime_die.png"), 13, 7, color_row),
        "swallow": load_sprite_sheet(os.path.join(slime_path, "slime_swallow.png"), 14, 7, color_row)
    }


def draw_character_preview(surf, sprites, anim_time, center_x, center_y):
    """Draw animated character preview."""
    # Use idle_main animation for preview
    frames = sprites.get("idle_main", [])
    if not frames:
        return
    
    # Animate through frames
    frame_rate = 0.2  # seconds per frame
    frame_index = int(anim_time / frame_rate) % len(frames)
    frame = frames[frame_index]
    
    # Draw the frame centered at the position
    rect = frame.get_rect(center=(center_x, center_y))
    surf.blit(frame, rect)
