"""
Portal class and portal loading functions for boss room entry.
"""
import os
import math
import random
import pygame

from config.constants import get_asset_path


# Portal frames cache
_portal_frames = None


def load_portal_frames():
    """Load portal spritesheet frames (called after pygame init)"""
    global _portal_frames
    if _portal_frames is not None:
        return _portal_frames
    
    portal_path = get_asset_path("data", "gfx", "PORTAL BLUE-Sheet.png")
    
    if not os.path.exists(portal_path):
        print(f"Warning: Portal spritesheet not found: {portal_path}")
        # Create placeholder frame
        s = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.circle(s, (0, 234, 255), (32, 32), 30)
        _portal_frames = [s]
        return _portal_frames
    
    try:
        sheet = pygame.image.load(portal_path).convert_alpha()
        sheet_w = sheet.get_width()
        sheet_h = sheet.get_height()
        
        # Assuming horizontal strip - detect frame count
        num_frames = 8
        frame_w = sheet_w // num_frames
        frame_h = sheet_h
        
        frames = []
        for i in range(num_frames):
            rect = pygame.Rect(i * frame_w, 0, frame_w, frame_h)
            frame = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
            frame.blit(sheet, (0, 0), rect)
            # Scale up for visibility (1.5x)
            scaled = pygame.transform.scale(frame, (int(frame_w * 1.5), int(frame_h * 1.5)))
            frames.append(scaled)
        
        _portal_frames = frames
        return _portal_frames
    except Exception as e:
        print(f"Error loading portal spritesheet: {e}")
        s = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.circle(s, (0, 234, 255), (32, 32), 30)
        _portal_frames = [s]
        return _portal_frames


class Portal:
    """Animated portal for entering boss room"""
    
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.w = 60
        self.h = 100
        self.anim_timer = 0.0
        self.frame_index = 0
        self.particles = []
        # Load portal frames
        self.frames = load_portal_frames()
        
    def update(self, dt):
        """Update portal animation"""
        self.anim_timer += dt
        
        # Update frame animation (10 FPS)
        if self.anim_timer >= 0.1:
            self.anim_timer -= 0.1
            self.frame_index = (self.frame_index + 1) % len(self.frames)
        
        # Spawn swirling particles (reduced for spritesheet portal)
        if random.random() < 0.15:
            angle = random.uniform(0, math.pi * 2)
            radius = random.uniform(25, 50)
            px = self.x + self.w // 2 + math.cos(angle) * radius
            py = self.y + self.h // 2 + math.sin(angle) * radius
            
            particle = {
                "x": px,
                "y": py,
                "angle": angle,
                "radius": radius,
                "lifetime": 0.8,
                "speed": random.uniform(15, 30)
            }
            self.particles.append(particle)
            
        # Update particles
        for p in self.particles[:]:
            p["lifetime"] -= dt
            p["angle"] += p["speed"] * dt * 0.1
            p["radius"] -= dt * 15
            
            if p["lifetime"] <= 0 or p["radius"] < 0:
                self.particles.remove(p)
            else:
                p["x"] = self.x + self.w // 2 + math.cos(p["angle"]) * p["radius"]
                p["y"] = self.y + self.h // 2 + math.sin(p["angle"]) * p["radius"]
                
    def rect(self):
        """Return collision rectangle"""
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)
        
    def check_collision(self, player_rect):
        """Check if player is touching portal"""
        return player_rect.colliderect(self.rect())
        
    def draw(self, surf, cam_x, cam_y):
        """Draw portal sprite with particle effects"""
        draw_x = self.x - cam_x
        draw_y = self.y - cam_y
        center_x = draw_x + self.w // 2
        center_y = draw_y + self.h // 2
        
        # Draw particles behind portal
        for p in self.particles:
            px = p["x"] - cam_x
            py = p["y"] - cam_y
            size = max(2, int(p["lifetime"] * 5))
            
            # Blue/cyan particles to match blue portal
            if p["radius"] > 30:
                color = (100, 150, 255)
            else:
                color = (0, 234, 255)
                
            pygame.draw.circle(surf, color, (int(px), int(py)), size)
        
        # Draw portal sprite centered
        if self.frames:
            frame = self.frames[self.frame_index]
            frame_w = frame.get_width()
            frame_h = frame.get_height()
            # Center the sprite on the portal position
            sprite_x = center_x - frame_w // 2
            sprite_y = center_y - frame_h // 2
            surf.blit(frame, (int(sprite_x), int(sprite_y)))
