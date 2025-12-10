"""
BossRoom class for the boss arena.
"""
import math
import pygame

from config.constants import (
    BOSS_ROOM_WIDTH, BOSS_ROOM_HEIGHT, TILE_SIZE, VICTORY_CREDITS
)
from .portal import load_portal_frames


class BossRoom:
    """Boss arena with static platforms and portals"""
    
    def __init__(self, tile_surface):
        self.tile_surf = tile_surface
        self.width = BOSS_ROOM_WIDTH
        self.height = BOSS_ROOM_HEIGHT
        
        # Static platforms
        self.platforms = []
        self._create_platforms()
        
        # Return portal (appears after boss defeat)
        self.return_portal = None
        self.portal_anim_timer = 0.0
        self.portal_frame_index = 0
        # Load portal frames
        self.portal_frames = load_portal_frames()
        
        # Victory rewards
        self.credit_orbs = []
        self.victory_claimed = False
        
    def _create_platforms(self):
        """Create static platform layout"""
        # 0: Floor
        self.platforms.append(pygame.Rect(0, self.height - TILE_SIZE * 2, 
                                          self.width, TILE_SIZE))
        # 1: Left
        self.platforms.append(pygame.Rect(50, self.height - TILE_SIZE * 7,
                                          TILE_SIZE * 6, TILE_SIZE))
        # 2: Center (High)
        self.platforms.append(pygame.Rect(self.width // 2 - TILE_SIZE * 3,
                                          self.height - TILE_SIZE * 12,
                                          TILE_SIZE * 6, TILE_SIZE))
        # 3: Right
        self.platforms.append(pygame.Rect(self.width - TILE_SIZE * 7 - 50,
                                          self.height - TILE_SIZE * 8,
                                          TILE_SIZE * 6, TILE_SIZE))
        # 4: Top Small Platform (The actual highest point)
        self.platforms.append(pygame.Rect(self.width // 2 - TILE_SIZE * 2,
                                          self.height - TILE_SIZE * 16,
                                          TILE_SIZE * 4, TILE_SIZE))
        
    def get_collision_tiles(self, rect):
        """Return platforms that collide with rect"""
        result = []
        for platform in self.platforms:
            if rect.colliderect(platform):
                result.append(platform)
        return result
        
    def activate_victory(self):
        """Called when boss is defeated - spawn rewards and portal"""
        if self.victory_claimed:
            return
            
        self.victory_claimed = True
        
        # 1. Spawn Portal at the Top Platform (Index 4)
        top_platform = self.platforms[4]
        self.return_portal = pygame.Rect(
            top_platform.centerx - 30,
            top_platform.top - 80,
            60, 80
        )

        # 2. Spawn Orbs at the FLOOR Platform (Index 0)
        floor_platform = self.platforms[0] 
        
        center_x = floor_platform.centerx
        ground_y = floor_platform.top - 15 
        
        for i in range(VICTORY_CREDITS):
            offset_x = (i - (VICTORY_CREDITS // 2)) * 30 
            
            orb = {
                "x": center_x + offset_x,
                "y": ground_y,
                "base_y": ground_y,
                "size": 14,
                "value": 10,
                "float_offset": i * 0.5,
                "grounded": True 
            }
            self.credit_orbs.append(orb)
            
    def update(self, dt):
        """Update room elements"""
        self.portal_anim_timer += dt
        
        # Update portal frame animation (10 FPS)
        if self.portal_frames and self.portal_anim_timer >= 0.1:
            self.portal_anim_timer -= 0.1
            self.portal_frame_index = (self.portal_frame_index + 1) % len(self.portal_frames)
        
        # Floating Logic
        for orb in self.credit_orbs:
            bob_height = 5
            bob_speed = 3
            orb["y"] = orb["base_y"] + math.sin(self.portal_anim_timer * bob_speed + orb["float_offset"]) * bob_height
                
    def collect_credit(self, player_rect):
        """Check if player collected any credit orbs, return TOTAL VALUE collected"""
        collected_value = 0
        for orb in self.credit_orbs[:]:
            orb_rect = pygame.Rect(orb["x"] - orb["size"]//2, 
                                  orb["y"] - orb["size"]//2,
                                  orb["size"], orb["size"])
            if player_rect.colliderect(orb_rect):
                self.credit_orbs.remove(orb)
                collected_value += orb.get("value", 1) 
        return collected_value
        
    def check_portal_entry(self, player_rect):
        """Check if player entered return portal"""
        if self.return_portal and player_rect.colliderect(self.return_portal):
            return True
        return False
        
    def draw(self, surf):
        """Draw room background, platforms, and effects"""
        # Dark background
        surf.fill((15, 10, 25))
        
        # Draw ominous pattern/grid
        grid_spacing = 40
        for x in range(0, self.width, grid_spacing):
            pygame.draw.line(surf, (30, 20, 40), (x, 0), (x, self.height), 1)
        for y in range(0, self.height, grid_spacing):
            pygame.draw.line(surf, (30, 20, 40), (0, y), (self.width, y), 1)
            
        # Draw platforms
        for platform in self.platforms:
            # Draw tiles
            for x in range(platform.left, platform.right, TILE_SIZE):
                surf.blit(self.tile_surf, (x, platform.top))
                
        # Draw credit orbs
        for orb in self.credit_orbs:
            glow_size = int(orb["size"] + 4)
            # Subtle pulse
            pulse = (math.sin(self.portal_anim_timer * 8) + 1) * 0.2 + 0.8
            r = min(255, int(255 * pulse))
            g = min(255, int(215 * pulse))
            glow_color = (r, g, 0)
            
            # Enhanced glow
            pygame.draw.circle(surf, glow_color, (int(orb["x"]), int(orb["y"])), glow_size)
            pygame.draw.circle(surf, (255, 215, 0), (int(orb["x"]), int(orb["y"])), int(orb["size"]))
            pygame.draw.circle(surf, (255, 255, 220), (int(orb["x"]), int(orb["y"])), max(1, int(orb["size"]) - 3))
            
        # Draw return portal
        if self.return_portal:
            self._draw_portal(surf, self.return_portal)
            
    def _draw_portal(self, surf, portal):
        """Draw animated portal sprite"""
        center_x = portal.centerx
        center_y = portal.centery
        
        # Draw portal sprite centered
        if self.portal_frames:
            frame = self.portal_frames[self.portal_frame_index]
            frame_w = frame.get_width()
            frame_h = frame.get_height()
            sprite_x = center_x - frame_w // 2
            sprite_y = center_y - frame_h // 2
            surf.blit(frame, (int(sprite_x), int(sprite_y)))
