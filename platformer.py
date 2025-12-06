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

# =========================
# PORTAL CLASS
# =========================
class Portal:
    """Animated portal for entering boss room"""
    
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.w = 60
        self.h = 100
        self.anim_timer = 0.0
        self.particles = []
        
    def update(self, dt):
        """Update portal animation"""
        self.anim_timer += dt
        
        # Spawn swirling particles
        if random.random() < 0.3:
            angle = random.uniform(0, math.pi * 2)
            radius = random.uniform(10, 35)
            px = self.x + self.w // 2 + math.cos(angle) * radius
            py = self.y + self.h // 2 + math.sin(angle) * radius
            
            particle = {
                "x": px,
                "y": py,
                "angle": angle,
                "radius": radius,
                "lifetime": 1.0,
                "speed": random.uniform(20, 40)
            }
            self.particles.append(particle)
            
        # Update particles
        for p in self.particles[:]:
            p["lifetime"] -= dt
            p["angle"] += p["speed"] * dt * 0.1
            p["radius"] -= dt * 20
            
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
        """Draw portal with particles and effects"""
        draw_x = self.x - cam_x
        draw_y = self.y - cam_y
        center_x = draw_x + self.w // 2
        center_y = draw_y + self.h // 2
        
        # Draw particles
        for p in self.particles:
            px = p["x"] - cam_x
            py = p["y"] - cam_y
            alpha = int(p["lifetime"] * 255)
            size = max(2, int(p["lifetime"] * 6))
            
            # Purple/pink/cyan gradient
            if p["radius"] > 20:
                color = (200, 100, 255)
            else:
                color = (0, 234, 255)
                
            pygame.draw.circle(surf, color, (int(px), int(py)), size)
            
        # Central portal glow
        for r in range(40, 0, -8):
            alpha = int((r / 40.0) * 80)
            glow_surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            color_val = int(100 + math.sin(self.anim_timer * 3) * 50)
            pygame.draw.circle(glow_surf, (color_val, 100, 255, alpha), (r, r), r)
            surf.blit(glow_surf, (center_x - r, center_y - r))
            
        # Outer ring
        ring_radius = 45 + math.sin(self.anim_timer * 2) * 3
        pygame.draw.circle(surf, (150, 50, 255), 
                          (int(center_x), int(center_y)), int(ring_radius), 4)
        
        # Inner ring
        inner_radius = 35 + math.sin(self.anim_timer * 3) * 2
        pygame.draw.circle(surf, (0, 234, 255),
                          (int(center_x), int(center_y)), int(inner_radius), 3)
                          
        # Pulsing center
        pulse = (math.sin(self.anim_timer * 5) + 1) * 0.5
        center_size = int(15 + pulse * 10)
        pygame.draw.circle(surf, (255, 200, 255),
                          (int(center_x), int(center_y)), center_size)

# =========================
# BOSS ROOM CLASS
# =========================
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
        
        # 1. Spawn Portal at the Top Platform (Index 4) - Keep this high up
        top_platform = self.platforms[4]
        self.return_portal = pygame.Rect(
            top_platform.centerx - 30,
            top_platform.top - 80, # Sit on top of the platform
            60, 80
        )

        # 2. Spawn Orbs at the FLOOR Platform (Index 0)
        floor_platform = self.platforms[0] 
        
        center_x = floor_platform.centerx
        # Position Y so they hover just above the floor tiles
        ground_y = floor_platform.top - 15 
        
        for i in range(VICTORY_CREDITS):
            # Spread them out horizontally
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
        
        # --- Floating Logic ---
        for orb in self.credit_orbs:
            # Gentle bobbing
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
        """Draw animated portal effect"""
        center_x = portal.centerx
        center_y = portal.centery
        
        # Rotating particles
        num_particles = 12
        radius = 35
        for i in range(num_particles):
            angle = (i / num_particles) * math.pi * 2 + self.portal_anim_timer * 2
            px = center_x + math.cos(angle) * radius
            py = center_y + math.sin(angle) * radius
            
            # Cyan particles
            size = 4 + math.sin(self.portal_anim_timer * 3 + i) * 2
            pygame.draw.circle(surf, (0, 234, 255), (int(px), int(py)), int(size))
            
        # Central glow
        for r in range(30, 0, -6):
            alpha = int((r / 30.0) * 100)
            glow_surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (0, 234, 255, alpha), (r, r), r)
            surf.blit(glow_surf, (center_x - r, center_y - r))
            
        # Portal frame
        pygame.draw.circle(surf, (0, 200, 220), (center_x, center_y), 40, 3)
        pygame.draw.circle(surf, (0, 150, 180), (center_x, center_y), 36, 2)

# =========================
# NECROMANCER BOSS CLASS
# =========================
class NecromancerBoss:
    """Boss enemy with flying movement, attack patterns, and vulnerability cycles"""
    
    def __init__(self, sprites, room_width, room_height, platforms):
        self.sprites = sprites
        self.room_width = room_width
        self.room_height = room_height
        self.platforms = platforms
        
        if sprites and "idle" in sprites and sprites["idle"]:
            ref = sprites["idle"][0]
            self.w = int(ref.get_width() * 0.4)  
            self.h = int(ref.get_height() * 0.75)
        else:
            self.w, self.h = 100, 150
            
        self.x = room_width // 2 - self.w // 2
        self.y = BOSS_FLIGHT_HEIGHT
        
        self.max_hp = BOSS_HP
        self.hp = self.max_hp
        self.alive = True
        
        # Visibility Flag for after death
        self.visible = True
        
        self.state = "ATTACKING"
        self.state_timer = random.uniform(ATTACK_DURATION_MIN, ATTACK_DURATION_MAX)
        
        # --- Recovery Timer to prevent damage while flying up ---
        self.recovery_timer = 0.0 

        # Damage Cap Counter
        self.damage_taken_this_phase = 0
        
        self.current_action = "idle"
        self.anim_timer = 0.0
        self.frame_index = 0
        self.facing_right = True
        
        self.attack_timer = 0.0
        self.attack_cooldown = 3.0
        self.projectiles = []
        self.platform_fires = []
        
        self.vx = 100.0
        self.target_y = BOSS_FLIGHT_HEIGHT
        
        self.invul_timer = 0.0
        
    def take_damage(self, amount):
        """Deal damage to boss, returns True if boss died"""
        # Can only take damage if TIRED, not invulnerable, and visible
        if self.invul_timer > 0 or self.state != "TIRED" or not self.visible:
            return False 
            
        # Check Damage Cap
        if self.damage_taken_this_phase >= 2:
            return False

        self.hp -= amount
        self.hp = max(0, self.hp)
        self.damage_taken_this_phase += 1
        
        self.invul_timer = 0.5
        self.current_action = "hit"
        self.frame_index = 0
        self.anim_timer = 0 # Reset anim timer so hit plays from start
        
        if self.hp <= 0:
            self.alive = False
            self.current_action = "death"
            self.frame_index = 0
            self.anim_timer = 0
            return True
            
        return False
        
    def update(self, dt, player_x, player_y, player_rect):
        """Update boss AI, movement, and attacks"""
        
        # --- Update Recovery Timer ---
        if self.recovery_timer > 0:
            self.recovery_timer -= dt

        # Handle Death Animation Correctly
        if not self.alive:
            if self.visible:
                self.anim_timer += dt
                if self.anim_timer > 0.15: # Slightly slower death anim
                    self.frame_index += 1
                    self.anim_timer = 0
                    
                    # Check if death animation finished
                    frames = self.sprites.get("death", [])
                    if frames and self.frame_index >= len(frames):
                        self.visible = False # Sprite disappears
                        
            return False # Dead boss doesn't deal damage
            
        # Normal Alive Logic
        self.invul_timer -= dt
        if self.invul_timer < 0:
            self.invul_timer = 0
            
        # Update state machine
        self.state_timer -= dt
        
        if self.state == "ATTACKING":
            if self.state_timer <= 0:
                # Transition to TIRED
                self.state = "TIRED"
                self.damage_taken_this_phase = 0 # Reset damage counter
                self.state_timer = TIRED_DURATION
                self.target_y = BOSS_TIRED_HEIGHT
                self.current_action = "idle"
                self.frame_index = 0
            else:
                self._update_attacking(dt, player_x, player_y, player_rect)
                
        elif self.state == "TIRED":
            if self.state_timer <= 0:
                # Transition back to ATTACKING
                self.state = "ATTACKING"
                
                # --- Set recovery timer to cover the flight up ---
                self.recovery_timer = 2.0 
                
                duration = random.uniform(ATTACK_DURATION_MIN, ATTACK_DURATION_MAX)
                if self.hp == 1:
                    duration /= ENRAGE_ATTACK_SPEED_MULTIPLIER
                self.state_timer = duration
                self.target_y = BOSS_FLIGHT_HEIGHT
                self.attack_timer = 0.5
                
        self._update_movement(dt, player_x)
        hit = self._update_projectiles(dt, player_rect)
        self._update_animation(dt)
        
        return hit
        
    def _update_attacking(self, dt, player_x, player_y, player_rect):
        self.attack_timer -= dt
        if self.attack_timer <= 0:
            attack_type = random.choice(["arrows", "fire"])
            if attack_type == "arrows":
                self._attack_magic_arrows(player_x, player_y)
                cooldown = 3.0
            else:
                self._attack_platform_fire()
                cooldown = 4.0
            
            if self.hp == 1:
                cooldown /= ENRAGE_ATTACK_SPEED_MULTIPLIER
            self.attack_timer = cooldown
            
    def _attack_magic_arrows(self, player_x, player_y):
        self.current_action = "cast"
        self.frame_index = 0
        self.anim_timer = 0
        num_arrows = random.randint(3, 5)
        boss_center_x = self.x + self.w // 2
        boss_center_y = self.y + self.h // 2
        for i in range(num_arrows):
            angle = math.atan2(player_y - boss_center_y, player_x - boss_center_x)
            angle += random.uniform(-0.3, 0.3)
            speed = 200.0
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            projectile = {
                "x": boss_center_x, "y": boss_center_y,
                "vx": vx, "vy": vy,
                "size": 8, "lifetime": 5.0
            }
            self.projectiles.append(projectile)
            
    def _attack_platform_fire(self):
        self.current_action = "attack1"
        self.frame_index = 0
        self.anim_timer = 0
        if not self.platforms: return
        num_fires = random.randint(1, 2)
        targets = random.sample(self.platforms, min(num_fires, len(self.platforms)))
        for platform in targets:
            fire = {
                "platform": platform,
                "warning_timer": 1.0,
                "fire_timer": 0.0,
                "fire_duration": 2.0,
                "active": False
            }
            self.platform_fires.append(fire)
            
    def _update_movement(self, dt, player_x):
        self.x += self.vx * dt
        if self.x <= 0:
            self.x = 0
            self.vx = abs(self.vx)
            self.facing_right = True
        elif self.x + self.w >= self.room_width:
            self.x = self.room_width - self.w
            self.vx = -abs(self.vx)
            self.facing_right = False
            
        y_diff = self.target_y - self.y
        if abs(y_diff) > 2:
            self.y += y_diff * 2.0 * dt
        else:
            self.y = self.target_y
            
    def _update_projectiles(self, dt, player_rect):
        hit = False
        for proj in self.projectiles[:]:
            proj["x"] += proj["vx"] * dt
            proj["y"] += proj["vy"] * dt
            proj["lifetime"] -= dt
            proj_rect = pygame.Rect(proj["x"] - proj["size"]//2, 
                                    proj["y"] - proj["size"]//2,
                                    proj["size"], proj["size"])
            if proj_rect.colliderect(player_rect):
                self.projectiles.remove(proj)
                hit = True
                continue
            if (proj["lifetime"] <= 0 or 
                proj["x"] < -50 or proj["x"] > self.room_width + 50 or
                proj["y"] < -50 or proj["y"] > self.room_height + 50):
                self.projectiles.remove(proj)
                
        for fire in self.platform_fires[:]:
            if not fire["active"]:
                fire["warning_timer"] -= dt
                if fire["warning_timer"] <= 0:
                    fire["active"] = True
                    fire["fire_timer"] = fire["fire_duration"]
            else:
                fire["fire_timer"] -= dt
                if fire["fire_timer"] <= 0:
                    self.platform_fires.remove(fire)
        return hit
        
    def _update_animation(self, dt):
        if self.current_action == "hit" and self.invul_timer > 0.1:
             pass # Let it play
        elif self.current_action in ["cast", "attack1"] and self.frame_index < 5:
             pass # Let start of attack play
        elif self.invul_timer <= 0:
             # Default state handling
             if self.current_action == "hit": 
                 self.current_action = "idle" # Recover
                 
        if self.current_action not in self.sprites or not self.sprites[self.current_action]:
            return
            
        self.anim_timer += dt
        anim_speed = 0.1
        
        if self.anim_timer > anim_speed:
            self.frame_index += 1
            frames = self.sprites[self.current_action]
            
            # Loop logic
            if self.frame_index >= len(frames):
                if self.current_action in ["hit", "cast", "attack1", "attack2"]:
                    self.current_action = "idle"
                    self.frame_index = 0
                else:
                    self.frame_index = 0
            self.anim_timer = 0.0
            
    def check_platform_fire_damage(self, player_rect):
        check_rect = player_rect.inflate(0, 4)
        for fire in self.platform_fires:
            if fire["active"] and check_rect.colliderect(fire["platform"]):
                return True
        return False
        
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)
        
    def draw(self, surf):
        # Draw projectiles and fire regardless of boss visibility (they persist)
        for proj in self.projectiles:
            color = (200, 100, 255)
            pygame.draw.circle(surf, color, (int(proj["x"]), int(proj["y"])), proj["size"])
            pygame.draw.circle(surf, (255, 200, 255), (int(proj["x"]), int(proj["y"])), proj["size"]//2)
            
        for fire in self.platform_fires:
            plat = fire["platform"]
            if not fire["active"]:
                alpha = int((math.sin(fire["warning_timer"] * 10) + 1) * 127)
                warning_surf = pygame.Surface((plat.width, 4), pygame.SRCALPHA)
                warning_surf.fill((255, 0, 0, alpha))
                surf.blit(warning_surf, (plat.x, plat.y - 6))
            else:
                for i in range(0, plat.width, 20):
                    flame_height = 15 + math.sin(fire["fire_timer"] * 5 + i) * 5
                    flame_x = plat.x + i
                    flame_y = plat.y - flame_height
                    colors = [(255, 100, 0), (255, 200, 0), (255, 50, 0)]
                    color = random.choice(colors)
                    pygame.draw.polygon(surf, color, [
                        (flame_x, plat.y), (flame_x + 10, plat.y), (flame_x + 5, flame_y)
                    ])
        
        # Only draw boss sprite if visible
        if self.visible:
            if self.current_action in self.sprites and self.sprites[self.current_action]:
                frames = self.sprites[self.current_action]
                if frames:
                    # Clamp frame index just in case
                    idx = min(self.frame_index, len(frames)-1)
                    img = frames[idx]
                    
                    if not self.facing_right:
                        img = pygame.transform.flip(img, True, False)
                        
                    draw_x = self.x + (self.w // 2) - (img.get_width() // 2)
                    draw_y = self.y + self.h - img.get_height()
                    surf.blit(img, (int(draw_x), int(draw_y)))
            
            # --- Sweat Effect when TIRED ---
            if self.state == "TIRED":
                # Create droplets relative to boss head
                time_val = pygame.time.get_ticks() / 200.0
                center_head_x = self.x + self.w // 2
                head_top_y = self.y + 10
                
                # Draw 3 drops
                for i in range(3):
                    # Drops fall down (modulo) and wiggle x (sin)
                    drop_y_offset = (time_val * 20 + i * 15) % 30
                    drop_x_offset = math.sin(time_val + i) * 20
                    
                    # Blue/Cyan sweat color
                    sweat_color = (0, 200, 255)
                    
                    # Draw small vertical ellipse
                    drop_rect = pygame.Rect(center_head_x + drop_x_offset - 3, head_top_y + drop_y_offset, 6, 9)
                    pygame.draw.ellipse(surf, sweat_color, drop_rect)

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

# Dash Constants (NEW)
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

# DEFAULT KEYBINDINGS
DEFAULT_KEYBINDS = {
    "p1_left": pygame.K_a,
    "p1_right": pygame.K_d,
    "p1_jump": pygame.K_w, # Alternatively K_SPACE, but defaulting to WASD
    "p1_slam": pygame.K_s,
    "p2_left": pygame.K_j,
    "p2_right": pygame.K_l,
    "p2_jump": pygame.K_i,
    "p2_slam": pygame.K_k
}

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
    "slam":  {"name": "Graviton", "base_cost": 80, "cost_mult": 1.4, "max": 10, "desc": "-8% Slam/Dash Cooldown"}
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
        self.keybinds = DEFAULT_KEYBINDS.copy() # Initialize with defaults
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

class SectionHeader:
    def __init__(self, x, y, text, font, color=COL_ACCENT_1):
        self.text = text
        self.font = font
        self.color = color
        # Create a rect for layout calculation, though we won't click it
        text_surf = font.render(text, True, color)
        self.rect = text_surf.get_rect(center=(x, y))
        # Add padding for visual spacing
        self.rect.height += 20 

    def handle_event(self, event):
        pass # Headers ignore events, preventing the crash

    def draw(self, surf):
        # Draw a cool underline
        line_y = self.rect.centery + 10
        center_x = self.rect.centerx
        
        # Draw text with shadow
        draw_text_shadow(surf, self.font, self.text, center_x, self.rect.centery - 5, 
                         center=True, col=self.color)
        
        # Neon line fading out to sides
        width = 200
        pygame.draw.line(surf, self.color, (center_x - width//2, line_y), (center_x + width//2, line_y), 2)

class KeybindButton:
    def __init__(self, rect, action_name, key_code, font, update_callback):
        self.rect = pygame.Rect(rect)
        self.action_name = action_name
        self.key_code = key_code
        self.font = font
        self.update_callback = update_callback
        self.listening = False
        self.hover = False
        
    def handle_event(self, event):
        if self.listening:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_DELETE:
                    self.listening = False
                else:
                    self.key_code = event.key
                    self.update_callback(self.key_code)
                    self.listening = False
                return True # Event Consumed

        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.listening = True
                return True # Consume click
        return False

    def draw(self, surf):
        # Logic for colors based on state
        if self.listening:
            # PULSING PINK GLOW
            pulse = (math.sin(pygame.time.get_ticks() / 150) + 1) * 0.5 # 0.0 to 1.0
            border_col = COL_ACCENT_2 # Hot Pink
            # Interpolate background brightness
            bg_base = 40
            bg_add = int(40 * pulse)
            bg_col = (bg_base + bg_add, 20, 40) # Reddish tint
            text_col = (255, 200, 200)
            key_str = "DELETE TO CANCEL"
        else:
            # STANDARD / HOVER STATE
            if self.hover:
                border_col = COL_ACCENT_1 # Cyan
                bg_col = (30, 30, 50)
                text_col = (255, 255, 255)
            else:
                border_col = (60, 60, 80) # Dark Blue/Grey
                bg_col = COL_UI_BG
                text_col = (200, 200, 200)
            key_str = pygame.key.name(self.key_code).upper()

        # 1. Draw Background Box
        pygame.draw.rect(surf, bg_col, self.rect, border_radius=6)
        
        # 2. Draw Border (Thicker if listening)
        width = 3 if self.listening else 1
        pygame.draw.rect(surf, border_col, self.rect, width, border_radius=6)

        # 3. Draw Action Name (Left Side)
        label_surf = self.font.render(self.action_name, True, (180, 180, 190))
        surf.blit(label_surf, (self.rect.x + 15, self.rect.centery - label_surf.get_height()//2))

        # 4. Draw Key Name (Right Side)
        key_surf = self.font.render(key_str, True, border_col) # Key takes the accent color
        
        # Add a background pill for the key text for contrast
        key_bg_rect = key_surf.get_rect(midright=(self.rect.right - 15, self.rect.centery))
        key_bg_rect.inflate_ip(20, 10) # Add padding
        
        # Draw key pill background
        pygame.draw.rect(surf, (10, 10, 15), key_bg_rect, border_radius=4)
        if self.listening:
             pygame.draw.rect(surf, border_col, key_bg_rect, 1, border_radius=4)

        # Blit text centered on the pill
        key_rect = key_surf.get_rect(center=key_bg_rect.center)
        surf.blit(key_surf, key_rect)

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
                if self.broadcasting and not self.connected: self.scanner.broadcast(self.remote_lobby_mode or MODE_VERSUS)
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

    def __init__(self, color, x, y, stats=None, sprite_dict=None, ability="Slam"):
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
        
        self.ability_type = ability
        
        self.stats_speed_lvl = stats.get("speed", 0) if stats else 0
        self.stats_jump_lvl = stats.get("jump", 0) if stats else 0
        self.stats_hp_lvl = stats.get("hp", 0) if stats else 0
        self.stats_slam_lvl = stats.get("slam", 0) if stats else 0

        self.max_hp = 3 + self.stats_hp_lvl
        self.hp = self.max_hp
        self.invul_timer = 0.0
        self.flash_on_invul = False 
        self.knockback_timer = 0.0

        self.speed_val = BASE_PLAYER_SPEED * (1.0 + 0.05 * self.stats_speed_lvl)
        self.jump_val = BASE_JUMP_VEL * (1.0 + 0.03 * self.stats_jump_lvl)
        
        # Cooldown reduction applies to both Slam and Dash
        cd_multiplier = (1.0 - 0.08 * self.stats_slam_lvl)
        self.slam_cd_val = max(0.1, BASE_SLAM_COOLDOWN * cd_multiplier)
        self.dash_cd_val = max(0.1, BASE_DASH_COOLDOWN * cd_multiplier)

        self.on_wall = False
        self.wall_dir = 0
        self.facing_right = True
        self.coyote_timer = 0.0
        self.jump_buffer_timer = 0.0
        self.jump_was_pressed = False
        
        # Slam specific
        self.slam_active = False
        self.slam_cooldown = 0.0
        self.slam_start_y = 0.0
        self.pending_slam_impact = False
        self.slam_impact_power = 0.0
        
        # Dash specific
        self.dash_active = False
        self.dash_timer = 0.0
        self.dash_cooldown = 0.0
        self.dash_speed = BASE_DASH_SPEED
        self.dash_duration = BASE_DASH_DURATION
        
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

        # --- KNOCKBACK LOGIC ---
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
        if self.slam_active or self.dash_active: self.trail.append([self.x, self.y, 200])
        if self.invul_timer > 0: self.invul_timer -= dt

        for t in self.trail:
            t[2] -= 1000 * dt
        self.trail = [t for t in self.trail if t[2] > 0]

        was_on_ground = self.on_ground
        self.pending_slam_impact = False
        
        # Update Cooldowns
        if self.slam_cooldown > 0.0:
            self.slam_cooldown = max(0.0, self.slam_cooldown - dt)
        if self.dash_cooldown > 0.0:
            self.dash_cooldown = max(0.0, self.dash_cooldown - dt)
        
        # Coyote time & Jump Buffer
        if self.on_ground: self.coyote_timer = self.COYOTE_TIME
        else: self.coyote_timer = max(0.0, self.coyote_timer - dt)

        if input_jump and not self.jump_was_pressed: self.jump_buffer_timer = self.JUMP_BUFFER
        else: self.jump_buffer_timer = max(0.0, self.jump_buffer_timer - dt)
        self.jump_was_pressed = input_jump

        # MOVEMENT PHYSICS
        desired_vx = 0.0
        
        # Only allow movement if not dashing
        if not self.is_dying and self.knockback_timer <= 0 and not self.dash_active: 
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
            elif not self.dash_active:
                self.vx = 0 if self.is_dying else desired_vx
        else: 
            # Air control (disabled during dash)
            if self.knockback_timer > 0:
                pass 
            elif not self.dash_active:
                self.vx += (desired_vx - self.vx) * self.AIR_CONTROL * dt * 10.0

        # Ability Logic: Slam or Dash
        can_use_ability = (not self.is_dying) and (self.knockback_timer <= 0)
        
        # SLAM LOGIC
        if self.ability_type == "Slam" and can_use_ability:
            can_slam = (not self.on_ground) and (not self.slam_active) and (self.slam_cooldown <= 0.0)
            if input_slam and can_slam:
                self.slam_active = True
                self.slam_start_y = self.y
                self.vy = BASE_SLAM_SPEED
                spawn_dust(self.x + self.w/2, self.y, count=5, color=COL_ACCENT_1)
        
        # DASH LOGIC
        elif self.ability_type == "Dash" and can_use_ability:
            can_dash = (not self.dash_active) and (self.dash_cooldown <= 0.0)
            if input_slam and can_dash:
                self.dash_active = True
                self.dash_timer = self.dash_duration
                self.dash_cooldown = self.dash_cd_val
                
                # Determine Dash Direction
                dash_dir = 1 if self.facing_right else -1
                if input_left: dash_dir = -1
                if input_right: dash_dir = 1
                self.facing_right = (dash_dir == 1)
                
                self.vx = dash_dir * self.dash_speed
                self.vy = 0 # Defy gravity initially
                spawn_dust(self.x + self.w/2, self.y + self.h/2, count=8, color=COL_ACCENT_2)

        # Update Dash State
        if self.dash_active:
            self.dash_timer -= dt
            self.vy = 0 # Sustain gravity defiance
            # Maintain dash speed
            dash_dir = 1 if self.facing_right else -1
            self.vx = dash_dir * self.dash_speed
            
            if self.dash_timer <= 0:
                self.dash_active = False
                self.vx *= 0.5 # Slow down after dash
                
        # Gravity & Wall Logic (Only if not dashing)
        if not self.dash_active:
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
        elif self.dash_active:
             # Reuse move or slam frame for dash, or dedicated if existed
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

        # --- Slam/Dash Animation ---
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
        if self.invul_timer > 0 or self.slam_active or self.is_dying or not self.alive or self.dash_active:
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
            # Use Pink color for dash trails to differentiate
            c = self.color
            if self.dash_active: c = COL_ACCENT_2 
            
            s.fill(c)
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
        self.health_orbs = []
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
        
        # Boss portal (spawns at x=2000)
        self.portal = None
        self.portal_spawned = False

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
             rect = pygame.Rect(ox, new_y - 3 * TILE_SIZE, orb_size, orb_size)
             
             # 8% Chance to spawn a Health Orb instead of a Point Orb
             if self.rng.random() < 0.08: 
                 self.health_orbs.append(rect)
             else:
                 self.orbs.append(rect)

        if not self.portal_spawned and self.generated_right_x >= 2000:
            portal_y = new_y - 100  # Above the platform
            self.portal = Portal(PORTAL_SPAWN_DISTANCE, portal_y)
            self.portal_spawned = True

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
        self.health_orbs = [h for h in self.health_orbs if h.right > cleanup_x] # <--- NEW: Cleanup
        self.enemies = [e for e in self.enemies if e.alive and e.x > cleanup_x]
        
        for c in self.dropped_credits: c.update(dt, self)
        self.dropped_credits = [c for c in self.dropped_credits if c.life > 0 and c.x > cleanup_x]
        
        # Update portal animation
        if self.portal:
            self.portal.update(dt)

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
        
        # Point Orbs (Gold)
        for orb in self.orbs:
            cx = orb.x - cam_x + orb.w // 2
            cy = orb.y - cam_y + orb.h // 2 + bob
            pygame.draw.circle(surf, COL_ACCENT_3, (cx, cy), orb.w // 2)
            pygame.draw.circle(surf, (255, 255, 200), (cx, cy), orb.w // 2 + 2, 1)

        # Draw Health Orbs (Green with a Cross)
        for horb in self.health_orbs:
            cx = horb.x - cam_x + horb.w // 2
            cy = horb.y - cam_y + horb.h // 2 + bob
            # Green Body
            pygame.draw.circle(surf, (50, 255, 50), (cx, cy), horb.w // 2)
            # White Border
            pygame.draw.circle(surf, (255, 255, 255), (cx, cy), horb.w // 2 + 2, 1)
            # Small White Cross logic
            cr_sz = 3
            pygame.draw.rect(surf, (255, 255, 255), (cx - 1, cy - cr_sz, 2, cr_sz*2))
            pygame.draw.rect(surf, (255, 255, 255), (cx - cr_sz, cy - 1, cr_sz*2, 2))

        for c in self.dropped_credits: c.draw(surf, cam_x, cam_y)
        for e in self.enemies: e.draw(surf, cam_x, cam_y)
        
        # Draw boss portal
        if self.portal:
            self.portal.draw(surf, cam_x, cam_y)

# =========================
# CHARACTER SELECTION
# =========================
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

    # Update filename to the requested OGG file
    MENU_BGM_PATH = get_asset_path("data", "sfx", "pck404_cosy_bossa.ogg")
    
    def play_menu_music():
        """Helper to restart menu music safely"""
        if os.path.exists(MENU_BGM_PATH):
            try:
                # Only reload if it's not already playing to avoid stutter on loop
                # However, since we switch tracks in game, we force load here usually.
                pygame.mixer.music.load(MENU_BGM_PATH)
                pygame.mixer.music.set_volume(settings.music_volume * settings.master_volume)
                pygame.mixer.music.play(-1)
            except Exception as e:
                print(f"Music load failed: {e}")

    # Play immediately on launch
    play_menu_music()
    
    # --- WRAPPER TO RESTORE MUSIC AFTER GAME ---
    def start_game_wrapper(*args, **kwargs):
        """Launches game, then restores menu music when game exits."""
        start_game(*args, **kwargs)
        # When start_game returns, we are back in the menu
        play_menu_music()
    
    main_buttons = []
    settings_widgets = []
    shop_buttons = []
    settings_scroll = 0.0
    mp_buttons = []
    mp_mode = MODE_VERSUS
    show_kick_confirm = False
    mp_connection_type = "local"  # "local" or "lan"
    
    # NEW: Keybind UI
    controls_widgets = []
    controls_scroll = 0.0

    # Initialize with placeholder text
    mp_ip_input = TextInput(pygame.Rect(140, 170, 200, 30), font_small, "", "Enter IP Address...")
    
    room_list = {}  # Dict of {ip: mode}
    selected_room = None
    
    global_anim_timer = 0.0
    
    # Character Selection State
    char_select_buttons = []
    selected_color_index = 3  # Default to Blue
    selected_ability_index = 0  # Default to Slam
    char_preview_sprites = None
    char_preview_time = 0.0
    
    # Multiplayer Character Selection State
    mp_char_buttons = []
    p1_color_index = 3  # Default to Blue
    p1_ability_index = 0
    p2_color_index = 1  # Default to Red
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
        
        # Load sprites for the currently selected color
        color_row = CHARACTER_COLORS[selected_color_index]["row"]
        char_preview_sprites = load_character_sprites(slime_path, color_row)
        
        # Arrow buttons for color selection
        def prev_color():
            nonlocal selected_color_index
            selected_color_index = (selected_color_index - 1) % len(CHARACTER_COLORS)
            rebuild_character_select()
        
        def next_color():
            nonlocal selected_color_index
            selected_color_index = (selected_color_index + 1) % len(CHARACTER_COLORS)
            rebuild_character_select()
        
        # Arrow buttons for ability selection
        def prev_ability():
            nonlocal selected_ability_index
            selected_ability_index = (selected_ability_index - 1) % len(CHARACTER_ABILITIES)
        
        def next_ability():
            nonlocal selected_ability_index
            selected_ability_index = (selected_ability_index + 1) % len(CHARACTER_ABILITIES)
        
        # Start game with selected character
        def start_with_selection():
            # Create custom sprite dict for selected color
            custom_sprites = load_character_sprites(slime_path, CHARACTER_COLORS[selected_color_index]["row"])
            ability_name = CHARACTER_ABILITIES[selected_ability_index]["name"]
            
            start_game_wrapper(settings, window, canvas, font_small, font_med, font_big, 
                             custom_sprites, player2_sprite, enemy_sprite_dict, tile_surf, 
                             wall_surf, lb, network, ROLE_LOCAL_ONLY, MODE_SINGLE, None, 
                             local_two_players=False, bg_obj=night_bg, 
                             p1_ability=ability_name)
        
        # Color selector arrows (positioned below the preview)
        char_select_buttons.append(Button(pygame.Rect(180, 220, 40, 35), "<", font_med, prev_color))
        char_select_buttons.append(Button(pygame.Rect(420, 220, 40, 35), ">", font_med, next_color))
        
        # Ability selector arrows
        char_select_buttons.append(Button(pygame.Rect(180, 290, 40, 35), "<", font_med, prev_ability))
        char_select_buttons.append(Button(pygame.Rect(420, 290, 40, 35), ">", font_med, next_ability))
        
        # Bottom buttons
        char_select_buttons.append(Button(pygame.Rect(110, 380, 140, 45), "RETURN", font_med, lambda: set_state(STATE_MAIN_MENU)))
        char_select_buttons.append(Button(pygame.Rect(390, 380, 140, 45), "START", font_med, start_with_selection, accent=COL_ACCENT_3))

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

        # --- Audio & Display Settings ---
        add_slider("Master Volume", lambda: settings.master_volume, lambda v: (setattr(settings, "master_volume", v), settings.apply_audio()), 0.0, 1.0)
        add_slider("Music Volume", lambda: settings.music_volume, lambda v: (setattr(settings, "music_volume", v), settings.apply_audio()), 0.0, 1.0)
        add_slider("SFX Volume", lambda: settings.sfx_volume, lambda v: setattr(settings, "sfx_volume", v), 0.0, 1.0)
        add_toggle("Screen Mode", ["Window", "Fullscreen", "Borderless"], lambda: settings.screen_mode, lambda idx: (setattr(settings, "screen_mode", idx), apply_screen_mode(window, idx)))
        
        y += 20 
        
        # --- Navigation Buttons ---
        button_width = 200
        button_height = 45
        
        # Go to Keybinds Menu
        rect_controls = pygame.Rect(VIRTUAL_W // 2 - button_width // 2, y, button_width, button_height)
        settings_widgets.append(Button(rect_controls, "Change keybinds", font_med, lambda: set_state(STATE_CONTROLS), accent=COL_ACCENT_3))
        
        y += button_height + 20

        # Return to Main Menu
        rect_return = pygame.Rect(VIRTUAL_W // 2 - button_width // 2, y, button_width, button_height)
        settings_widgets.append(Button(rect_return, "Return to Main Menu", font_med, lambda: set_state(STATE_MAIN_MENU)))

    def rebuild_controls_menu():
        nonlocal controls_scroll
        controls_widgets.clear()
        controls_scroll = 0.0
        
        y = 80
        
        # Helper for keybind updates
        def make_update_callback(action_key):
            def callback(new_code):
                settings.keybinds[action_key] = new_code
            return callback
        
        # --- Player 1 Configuration (Left Side) ---
        p1_x = 30
        p1_width = 280
        p1_button_height = 40
        p1_spacing = 12
        
        controls_widgets.append(SectionHeader(p1_x + p1_width // 2, y, "PLAYER 1", font_med, COL_ACCENT_1))
        p1_y = y + 40
        
        p1_actions = [("p1_left", "Left"), ("p1_right", "Right"), ("p1_jump", "Jump"), ("p1_slam", "Ability")]
        for key, name in p1_actions:
            current_code = settings.keybinds.get(key, DEFAULT_KEYBINDS[key])
            rect = pygame.Rect(p1_x, p1_y, p1_width, p1_button_height)
            btn = KeybindButton(rect, name, current_code, font_small, make_update_callback(key))
            controls_widgets.append(btn)
            p1_y += p1_button_height + p1_spacing
        
        # --- Player 2 Configuration (Right Side) ---
        p2_x = VIRTUAL_W - p1_width - 30
        p2_width = 280
        p2_button_height = 40
        p2_spacing = 12
        
        controls_widgets.append(SectionHeader(p2_x + p2_width // 2, y, "PLAYER 2", font_med, COL_ACCENT_2))
        p2_y = y + 40
        
        p2_actions = [("p2_left", "Left"), ("p2_right", "Right"), ("p2_jump", "Jump"), ("p2_slam", "Ability")]
        for key, name in p2_actions:
            current_code = settings.keybinds.get(key, DEFAULT_KEYBINDS[key])
            rect = pygame.Rect(p2_x, p2_y, p2_width, p2_button_height)
            btn = KeybindButton(rect, name, current_code, font_small, make_update_callback(key))
            controls_widgets.append(btn)
            p2_y += p2_button_height + p2_spacing
        
        # Update y to be after the lowest player config
        y = max(p1_y, p2_y) + 30
        
        # --- Reset Button ---
        def reset_defaults():
            settings.keybinds = DEFAULT_KEYBINDS.copy()
            rebuild_controls_menu()
        
        button_width = 180
        button_height = 40
        rect_reset = pygame.Rect(VIRTUAL_W // 2 - button_width // 2, y, button_width, button_height)
        controls_widgets.append(Button(rect_reset, "RESET DEFAULTS", font_med, reset_defaults, accent=(255, 80, 80)))
        
        y += button_height + 20
        
        # --- Return to Settings Button ---
        rect_back = pygame.Rect(VIRTUAL_W // 2 - button_width // 2, y, button_width, button_height)
        controls_widgets.append(Button(rect_back, "Back to Settings", font_med, lambda: set_state(STATE_SETTINGS)))

    def rebuild_mp_lobby():
        """Initial multiplayer menu: Create Room or Join Room"""
        mp_buttons.clear()
        
        y = 150
        # Create Room button
        mp_buttons.append(Button(pygame.Rect(VIRTUAL_W // 2 - 100, y, 200, 50), "Create Room", font_med, 
                                 lambda: set_state(STATE_MP_MODE), accent=COL_ACCENT_3))
        y += 70
        # Join Room button
        mp_buttons.append(Button(pygame.Rect(VIRTUAL_W // 2 - 100, y, 200, 50), "Join Room", font_med, 
                                 lambda: set_state(STATE_MP_ROOM_BROWSER)))
        
        # Return button
        mp_buttons.append(Button(pygame.Rect(20, VIRTUAL_H - 50, 80, 30), "Return", font_small, 
                                 lambda: set_state(STATE_MAIN_MENU)))
    
    def rebuild_mp_mode():
        """Choose Local or LAN for room creation"""
        mp_buttons.clear()
        
        y = 150
        # Local button
        def choose_local():
            nonlocal mp_connection_type
            mp_connection_type = "local"
            set_state(STATE_MP_CHARACTER_SELECT)
        
        mp_buttons.append(Button(pygame.Rect(VIRTUAL_W // 2 - 100, y, 200, 50), "LOCAL", font_med, 
                                 choose_local, accent=COL_ACCENT_1))
        y += 70
        
        # LAN button
        def choose_lan():
            nonlocal mp_connection_type
            mp_connection_type = "lan"
            network.host()  # Start hosting
            set_state(STATE_MP_CHARACTER_SELECT)
        
        mp_buttons.append(Button(pygame.Rect(VIRTUAL_W // 2 - 100, y, 200, 50), "LAN", font_med, 
                                 choose_lan, accent=COL_ACCENT_3))
        
        # Return button
        mp_buttons.append(Button(pygame.Rect(20, VIRTUAL_H - 50, 80, 30), "Return", font_small, 
                                 lambda: set_state(STATE_MP_LOBBY)))
    
    def rebuild_mp_character_select():
        """2-player character selection menu"""
        nonlocal p1_preview_sprites, p2_preview_sprites
        mp_char_buttons.clear()
        
        # Load preview sprites
        p1_preview_sprites = load_character_sprites(slime_path, CHARACTER_COLORS[p1_color_index]["row"])
        p2_preview_sprites = load_character_sprites(slime_path, CHARACTER_COLORS[p2_color_index]["row"])
        
        # P1 Color arrows
        def p1_prev_color():
            nonlocal p1_color_index
            p1_color_index = (p1_color_index - 1) % len(CHARACTER_COLORS)
            rebuild_mp_character_select()
        
        def p1_next_color():
            nonlocal p1_color_index
            p1_color_index = (p1_color_index + 1) % len(CHARACTER_COLORS)
            rebuild_mp_character_select()
        
        # P1 Ability arrows
        def p1_prev_ability():
            nonlocal p1_ability_index
            p1_ability_index = (p1_ability_index - 1) % len(CHARACTER_ABILITIES)
        
        def p1_next_ability():
            nonlocal p1_ability_index
            p1_ability_index = (p1_ability_index + 1) % len(CHARACTER_ABILITIES)
        
        # P2 Color arrows (only for local mode)
        def p2_prev_color():
            nonlocal p2_color_index
            if mp_connection_type == "local":
                p2_color_index = (p2_color_index - 1) % len(CHARACTER_COLORS)
                rebuild_mp_character_select()
        
        def p2_next_color():
            nonlocal p2_color_index
            if mp_connection_type == "local":
                p2_color_index = (p2_color_index + 1) % len(CHARACTER_COLORS)
                rebuild_mp_character_select()
        
        # P2 Ability arrows (only for local mode)
        def p2_prev_ability():
            nonlocal p2_ability_index
            if mp_connection_type == "local":
                p2_ability_index = (p2_ability_index - 1) % len(CHARACTER_ABILITIES)
        
        def p2_next_ability():
            nonlocal p2_ability_index
            if mp_connection_type == "local":
                p2_ability_index = (p2_ability_index + 1) % len(CHARACTER_ABILITIES)
        
        # P1 buttons (left side)
        p1_x = 210  # Match P1 center position
        mp_char_buttons.append(Button(pygame.Rect(p1_x - 70, 220, 40, 35), "<", font_med, p1_prev_color))
        mp_char_buttons.append(Button(pygame.Rect(p1_x + 30, 220, 40, 35), ">", font_med, p1_next_color))
        mp_char_buttons.append(Button(pygame.Rect(p1_x - 70, 290, 40, 35), "<", font_med, p1_prev_ability))
        mp_char_buttons.append(Button(pygame.Rect(p1_x + 30, 290, 40, 35), ">", font_med, p1_next_ability))
        
        # P2 buttons (right side) - only enabled for local
        p2_x = 430  # Match P2 center position
        p2_color_left = Button(pygame.Rect(p2_x - 70, 220, 40, 35), "<", font_med, p2_prev_color)
        p2_color_right = Button(pygame.Rect(p2_x + 30, 220, 40, 35), ">", font_med, p2_next_color)
        p2_ability_left = Button(pygame.Rect(p2_x - 70, 290, 40, 35), "<", font_med, p2_prev_ability)
        p2_ability_right = Button(pygame.Rect(p2_x + 30, 290, 40, 35), ">", font_med, p2_next_ability)
        
        if mp_connection_type != "local":
            # Grey out P2 buttons for LAN mode
            p2_color_left.disabled = True
            p2_color_right.disabled = True
            p2_ability_left.disabled = True
            p2_ability_right.disabled = True
        
        mp_char_buttons.extend([p2_color_left, p2_color_right, p2_ability_left, p2_ability_right])
        
        # Start game button
        def start_mp_game():
            p1_sprites = load_character_sprites(slime_path, CHARACTER_COLORS[p1_color_index]["row"])
            p2_sprites = load_character_sprites(slime_path, CHARACTER_COLORS[p2_color_index]["row"])
            
            p1_ab = CHARACTER_ABILITIES[p1_ability_index]["name"]
            p2_ab = CHARACTER_ABILITIES[p2_ability_index]["name"]
            
            if mp_connection_type == "local":
                # Local multiplayer
                start_game_wrapper(settings, window, canvas, font_small, font_med, font_big, 
                                 p1_sprites, p2_sprites, enemy_sprite_dict, tile_surf, 
                                 wall_surf, lb, network, ROLE_LOCAL_ONLY, mp_mode, None, 
                                 local_two_players=True, bg_obj=night_bg,
                                 p1_ability=p1_ab, p2_ability=p2_ab)
            else:
                # LAN multiplayer - wait for other player or start if connected
                if network.connected:
                    network.send_start_game()
                    time.sleep(0.2)
                start_game_wrapper(settings, window, canvas, font_small, font_med, font_big, 
                                 p1_sprites, p2_sprites, enemy_sprite_dict, tile_surf, 
                                 wall_surf, lb, network, network.role, mp_mode, None, 
                                 local_two_players=False, bg_obj=night_bg,
                                 p1_ability=p1_ab, p2_ability=p2_ab)
        
        # Bottom buttons
        # Return button (left)
        def return_action():
            if mp_connection_type == "lan":
                network.close()
            set_state(STATE_MP_MODE)
        
        mp_char_buttons.append(Button(pygame.Rect(80, 380, 140, 45), "RETURN", font_med, return_action))
        
        # Mode toggle button (center)
        def toggle_mp_mode():
            nonlocal mp_mode
            mp_mode = MODE_COOP if mp_mode == MODE_VERSUS else MODE_VERSUS
            rebuild_mp_character_select()
        
        mode_text = f"Mode: {'Co-op' if mp_mode == MODE_COOP else 'Versus'}"
        mp_char_buttons.append(Button(pygame.Rect(250, 380, 140, 45), mode_text, font_med, toggle_mp_mode))
        
        # Start button (right)
        mp_char_buttons.append(Button(pygame.Rect(420, 380, 140, 45), "START", font_med, 
                                      start_mp_game, accent=COL_ACCENT_3))
    
    def rebuild_mp_room_browser():
        """Server list for joining rooms"""
        mp_buttons.clear()
        
        # Refresh button
        def refresh_action():
            nonlocal selected_room
            network.scanner.found_hosts = {}
            nonlocal room_list
            room_list = {}
            selected_room = None
        
        # Return button (left)
        mp_buttons.append(Button(pygame.Rect(80, VIRTUAL_H - 70, 140, 40), 
                                "Return", font_med, lambda: (network.close(), set_state(STATE_MP_LOBBY))))
        
        # Refresh button (center)
        mp_buttons.append(Button(pygame.Rect(VIRTUAL_W // 2 - 70, VIRTUAL_H - 70, 140, 40), 
                                "Refresh", font_med, refresh_action))
        
        # Join Room button (right) - disabled if no room selected
        def join_room_action():
            if selected_room:
                network.join(selected_room)
        
        join_btn = Button(pygame.Rect(VIRTUAL_W - 220, VIRTUAL_H - 70, 140, 40), 
                         "Join Room", font_med, join_room_action, accent=COL_ACCENT_3)
        
        if not selected_room:
            join_btn.disabled = True
        
        mp_buttons.append(join_btn)
    
    # This function is kept for backward compatibility but now just calls rebuild_mp_lobby
    def rebuild_mp_menu():
        rebuild_mp_lobby()

    def set_state(s):
        nonlocal game_state
        # IMPORTANT: Refresh save data whenever we change state (e.g. returning from game)
        # This ensures credits are updated in the UI immediately
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
    
    def stop(): nonlocal running; running = False

    rebuild_main_menu()
    rebuild_settings_menu()
    rebuild_controls_menu()
    rebuild_mp_menu()
    
    host_sync_timer = 0.0
    last_connected_status = False

    while running:
        # CLAMP DT to prevent physics explosions on first frame or lag spikes
        dt = clock.tick(settings.target_fps) / 1000.0
        dt = min(dt, 0.05) # Max 0.05s per frame (20 FPS min physics speed)
        global_anim_timer += dt

        # Check Music Status (Restart if stopped by game and back in menu)
        if game_state in (STATE_MAIN_MENU, STATE_SETTINGS, STATE_CONTROLS, STATE_SHOP, STATE_MULTIPLAYER_MENU, STATE_LEADERBOARD, 
                          STATE_CHARACTER_SELECT, STATE_MP_LOBBY, STATE_MP_MODE, STATE_MP_CHARACTER_SELECT, STATE_MP_ROOM_BROWSER):
            if not pygame.mixer.music.get_busy():
                play_menu_music()
        
        # Update character preview animation
        if game_state == STATE_CHARACTER_SELECT:
            char_preview_time += dt
        
        # Update MP character preview animation
        if game_state == STATE_MP_CHARACTER_SELECT:
            mp_char_preview_time += dt
        
        # Handle Window Scaling (Maintain Aspect Ratio)
        win_w, win_h = window.get_size()
        scale = min(win_w / VIRTUAL_W, win_h / VIRTUAL_H)
        scaled_w, scaled_h = int(VIRTUAL_W * scale), int(VIRTUAL_H * scale)
        offset_x, offset_y = (win_w - scaled_w) // 2, (win_h - scaled_h) // 2

        # Handle room browser scanning
        if game_state == STATE_MP_ROOM_BROWSER:
            network.scanner.listen()
            current_hosts = network.scanner.found_hosts
            if current_hosts != room_list: room_list = dict(current_hosts)
        
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
            elif game_state == STATE_CHARACTER_SELECT:
                for b in char_select_buttons: b.handle_event(ui_event)
                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE: set_state(STATE_MAIN_MENU)
            elif game_state == STATE_SHOP:
                for b in shop_buttons: b.handle_event(ui_event)
                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE: set_state(STATE_MAIN_MENU)
            elif game_state == STATE_SETTINGS:
                # Save settings only when exiting the menu
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
                
                # Prepare scrolling event
                sevt = ui_event
                if ui_event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and "pos" in ui_event.dict:
                    sevt = pygame.event.Event(ui_event.type, {**ui_event.dict, "pos": (ui_event.pos[0], ui_event.pos[1] + controls_scroll)})
                
                # Check if a widget wants to consume the event first (e.g., KeybindButton listening)
                consumed = False
                for w in controls_widgets:
                    if isinstance(w, KeybindButton) and w.listening:
                        if w.handle_event(sevt): 
                            consumed = True
                            break
                
                # If not consumed by a listening button, handle normal interactions
                if not consumed:
                    # Handle navigation (ESC to go back)
                    if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE: 
                        settings.save()
                        set_state(STATE_SETTINGS)
                    
                    # Handle other widget events (Clicks, hover)
                    else:
                        for w in controls_widgets:
                            if hasattr(w, "handle_event"):
                                w.handle_event(sevt)

            elif game_state == STATE_MULTIPLAYER_MENU:
                
                # --- Handle Kick Confirmation Modal ---
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
            
            elif game_state == STATE_MP_LOBBY:
                for b in mp_buttons: b.handle_event(ui_event)
                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE: set_state(STATE_MAIN_MENU)
            
            elif game_state == STATE_MP_MODE:
                for b in mp_buttons: b.handle_event(ui_event)
                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE: set_state(STATE_MP_LOBBY)
            
            elif game_state == STATE_MP_CHARACTER_SELECT:
                for b in mp_char_buttons: b.handle_event(ui_event)
                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE: 
                    if mp_connection_type == "lan":
                        network.close()
                    set_state(STATE_MP_MODE)
            
            elif game_state == STATE_MP_ROOM_BROWSER:
                # Handle room selection clicks
                if ui_event.type == pygame.MOUSEBUTTONDOWN and ui_event.button == 1:
                    if "pos" in ui_event.dict:
                        mx, my = ui_event.pos
                        # Server list area
                        list_rect = pygame.Rect(50, 70, VIRTUAL_W - 100, 250)
                        if list_rect.collidepoint(mx, my):
                            row_height = 40
                            index = int((my - 70) / row_height)
                            room_ips = list(room_list.keys())
                            if 0 <= index < len(room_ips):
                                selected_room = room_ips[index]
                                # Rebuild to update Join button state
                                rebuild_mp_room_browser()
                
                for b in mp_buttons: b.handle_event(ui_event)
                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_ESCAPE: 
                    network.close()
                    set_state(STATE_MP_LOBBY)

        if game_state == STATE_SETTINGS:
            if settings_widgets:
                max_bottom = max([w.rect.bottom for w in settings_widgets])
                max_scroll = max(0, max_bottom + 20 - VIRTUAL_H)
                settings_scroll = clamp(settings_scroll, 0, max_scroll)
        
        elif game_state == STATE_CONTROLS:
            if controls_widgets:
                bottoms = [w.rect.bottom for w in controls_widgets if hasattr(w, 'rect')]
                max_bottom = max(bottoms) if bottoms else 0
                max_scroll = max(0, max_bottom + 20 - VIRTUAL_H)
                controls_scroll = clamp(controls_scroll, 0, max_scroll)

        elif game_state == STATE_MULTIPLAYER_MENU: mp_ip_input.update(dt)

        # Rendering
        canvas.fill(COL_BG) # Clear with BG
        
        if game_state == STATE_MAIN_MENU:
            menu_scroll_x += dt * 60 # Auto scroll right
            day_bg.draw(canvas, menu_scroll_x) # Use Day Parallax
            draw_text_shadow(canvas, font_big, GAME_TITLE, VIRTUAL_W//2, 60, center=True, pulse=True, time_val=global_anim_timer)
            for b in main_buttons: b.draw(canvas, dt)
        
        elif game_state == STATE_CHARACTER_SELECT:
            # Draw background
            menu_scroll_x += dt * 60
            day_bg.draw(canvas, menu_scroll_x)
            
            # Draw title
            draw_text_shadow(canvas, font_big, "Character Select", VIRTUAL_W//2, 40, center=True)
            
            # Draw character preview circle background
            preview_center_x = VIRTUAL_W // 2
            preview_center_y = 140
            pygame.draw.circle(canvas, COL_UI_BG, (preview_center_x, preview_center_y), 60)
            pygame.draw.circle(canvas, COL_ACCENT_1, (preview_center_x, preview_center_y), 60, 3)
            
            # Draw animated character preview
            if char_preview_sprites:
                draw_character_preview(canvas, char_preview_sprites, char_preview_time, preview_center_x, preview_center_y)
            
            # Draw color selection section
            color_name = CHARACTER_COLORS[selected_color_index]["name"]
            draw_text_shadow(canvas, font_med, f"{color_name}", VIRTUAL_W//2, 237, center=True, col=COL_ACCENT_1)
            
            # Draw ability selection section
            ability = CHARACTER_ABILITIES[selected_ability_index]
            draw_text_shadow(canvas, font_med, f"{ability['name']}", VIRTUAL_W//2, 307, center=True, col=COL_ACCENT_1)
            
            # Draw ability description box
            desc_panel = pygame.Rect(VIRTUAL_W//2 - 150, 330, 300, 45)
            draw_panel(canvas, desc_panel)
            # Draw multi-line description
            desc_lines = ability['description'].split('\n')
            for i, line in enumerate(desc_lines):
                draw_text_shadow(canvas, font_small, line, VIRTUAL_W//2, 340 + i * 14, center=True, col=COL_TEXT)
            
            # Draw buttons
            for b in char_select_buttons: b.draw(canvas, dt)
        
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
            for w in settings_widgets:
                orig_y = w.rect.y
                w.rect.y = orig_y - settings_scroll
                if w.rect.bottom > 0 and w.rect.top < VIRTUAL_H: w.draw(canvas)
                w.rect.y = orig_y
            draw_text_shadow(canvas, font_big, "System Config", 20, 20)

        elif game_state == STATE_CONTROLS:
            draw_text_shadow(canvas, font_big, "CONTROLS", 20, 20)
            
            # Helper text
            draw_text_shadow(canvas, font_small, "Click to rebind. Press DELETE to Cancel.", VIRTUAL_W//2, 50, center=True, col=(150, 150, 180))

            for w in controls_widgets:
                orig_y = w.rect.y
                w.rect.y = orig_y - controls_scroll
                
                # Draw if visible on screen
                if w.rect.bottom > 0 and w.rect.top < VIRTUAL_H: 
                     w.draw(canvas)
                
                w.rect.y = orig_y # Restore original Y


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
                    for i, (room_ip, room_mode) in enumerate(list(room_list.items())[:6]):  # Show max 6 rooms
                        y_pos = 170 + i * 24
                        if y_pos > 240: break
                        row_rect = pygame.Rect(220, y_pos, 380, 20)
                        if room_ip == selected_room:
                            pygame.draw.rect(canvas, (40, 40, 60), row_rect)
                        elif row_rect.collidepoint(pygame.mouse.get_pos()[0] - offset_x, pygame.mouse.get_pos()[1] - offset_y): 
                             pygame.draw.rect(canvas, (30, 30, 40), row_rect)
                        canvas.blit(font_small.render(f"HOST: {room_ip}", False, COL_TEXT), (225, y_pos + 2))

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
        
        elif game_state == STATE_MP_LOBBY:
            # Simple menu with Create Room / Join Room
            menu_scroll_x += dt * 60
            day_bg.draw(canvas, menu_scroll_x)
            draw_text_shadow(canvas, font_big, "Multiplayer", VIRTUAL_W//2, 60, center=True, pulse=True, time_val=global_anim_timer)
            for b in mp_buttons: b.draw(canvas, dt)
        
        elif game_state == STATE_MP_MODE:
            # Local vs LAN choice
            menu_scroll_x += dt * 60
            day_bg.draw(canvas, menu_scroll_x)
            draw_text_shadow(canvas, font_big, "Choose Mode", VIRTUAL_W//2, 60, center=True)
            for b in mp_buttons: b.draw(canvas, dt)
        
        elif game_state == STATE_MP_CHARACTER_SELECT:
            # 2-player character selection
            menu_scroll_x += dt * 60
            day_bg.draw(canvas, menu_scroll_x)
            draw_text_shadow(canvas, font_big, "Character Select", VIRTUAL_W//2, 40, center=True)
            
            # P1 (Left side)
            p1_center_x = 210
            p1_center_y = 140
            pygame.draw.circle(canvas, COL_UI_BG, (p1_center_x, p1_center_y), 50)
            pygame.draw.circle(canvas, COL_ACCENT_1, (p1_center_x, p1_center_y), 50, 3)
            if p1_preview_sprites:
                draw_character_preview(canvas, p1_preview_sprites, mp_char_preview_time, p1_center_x, p1_center_y)
            draw_text_shadow(canvas, font_small, "P1", p1_center_x, 90, center=True, col=COL_ACCENT_1)
            
            # P1 selections
            p1_color = CHARACTER_COLORS[p1_color_index]["name"]
            p1_ability = CHARACTER_ABILITIES[p1_ability_index]["name"]
            draw_text_shadow(canvas, font_med, f"{p1_color}", p1_center_x, 237, center=True, col=COL_ACCENT_1)
            draw_text_shadow(canvas, font_med, f"{p1_ability}", p1_center_x, 307, center=True, col=COL_ACCENT_1)
            
            # P2 (Right side)
            p2_center_x = 430
            p2_center_y = 140
            
            if mp_connection_type == "lan":
                # Grey out for LAN, show "Waiting for player..."
                pygame.draw.circle(canvas, (30, 30, 40), (p2_center_x, p2_center_y), 50)
                pygame.draw.circle(canvas, (80, 80, 90), (p2_center_x, p2_center_y), 50, 3)
                draw_text_shadow(canvas, font_small, "P2", p2_center_x, 90, center=True, col=(100, 100, 110))
                draw_text_shadow(canvas, font_small, "Waiting for player...", p2_center_x, p2_center_y, center=True, col=(150, 150, 160))
                # Grey selections
                draw_text_shadow(canvas, font_med, "---", p2_center_x, 237, center=True, col=(80, 80, 90))
                draw_text_shadow(canvas, font_med, "---", p2_center_x, 307, center=True, col=(80, 80, 90))
            else:
                # Local mode - show P2 normally
                pygame.draw.circle(canvas, COL_UI_BG, (p2_center_x, p2_center_y), 50)
                pygame.draw.circle(canvas, COL_ACCENT_2, (p2_center_x, p2_center_y), 50, 3)
                if p2_preview_sprites:
                    draw_character_preview(canvas, p2_preview_sprites, mp_char_preview_time, p2_center_x, p2_center_y)
                draw_text_shadow(canvas, font_small, "P2", p2_center_x, 90, center=True, col=COL_ACCENT_2)
                
                # P2 selections
                p2_color = CHARACTER_COLORS[p2_color_index]["name"]
                p2_ability = CHARACTER_ABILITIES[p2_ability_index]["name"]
                draw_text_shadow(canvas, font_med, f"{p2_color}", p2_center_x, 237, center=True, col=COL_ACCENT_2)
                draw_text_shadow(canvas, font_med, f"{p2_ability}", p2_center_x, 307, center=True, col=COL_ACCENT_2)
            
            # Draw buttons
            for b in mp_char_buttons: b.draw(canvas, dt)
        
        elif game_state == STATE_MP_ROOM_BROWSER:
            # Server list
            menu_scroll_x += dt * 60
            day_bg.draw(canvas, menu_scroll_x)
            draw_text_shadow(canvas, font_big, "Server List", VIRTUAL_W//2, 30, center=True)
            
            # Draw server list panel
            list_rect = pygame.Rect(50, 70, VIRTUAL_W - 100, 250)
            draw_panel(canvas, list_rect)
            
            if room_list:
                y_offset = 80
                for i, (room_ip, room_mode) in enumerate(list(room_list.items())[:6]):  # Show max 6 rooms
                    room_rect = pygame.Rect(60, y_offset, VIRTUAL_W - 120, 35)
                    is_selected = (selected_room == room_ip)
                    
                    # Highlight selected
                    if is_selected:
                        pygame.draw.rect(canvas, (40, 40, 60), room_rect, border_radius=3)
                    
                    # Room info
                    draw_text_shadow(canvas, font_small, f"{room_ip}", 70, y_offset + 8, col=COL_ACCENT_3 if is_selected else COL_TEXT)
                    mode_text = "Co-op" if room_mode == MODE_COOP else "Versus"
                    draw_text_shadow(canvas, font_small, f"Mode: {mode_text}", VIRTUAL_W - 180, y_offset + 8, col=COL_ACCENT_1)
                    
                    y_offset += 40
            else:
                draw_text_shadow(canvas, font_med, "No servers found", VIRTUAL_W//2, 180, center=True, col=(100, 100, 110))
                draw_text_shadow(canvas, font_small, "Click Refresh to scan", VIRTUAL_W//2, 210, center=True, col=(80, 80, 90))
            
            # Draw buttons
            for b in mp_buttons: b.draw(canvas, dt)

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
def start_game(settings, window, canvas, font_small, font_med, font_big, player1_sprites, player2_sprites, enemy_sprite_dict, tile_surf, wall_surf, lb, network, net_role, mode, mp_name_hint=None, local_two_players=False, bg_obj=None, p1_ability="Slam", p2_ability="Slam"):
    clock = pygame.time.Clock()
    
    # --- NEW MUSIC LOGIC START ---
    # Stop previous music (Menu music)
    pygame.mixer.music.stop()
    
    # Define and load Game BGM
    GAME_BGM_PATH = get_asset_path("data", "sfx", "pck404_lets_play.ogg")
    
    if os.path.exists(GAME_BGM_PATH):
        try:
            pygame.mixer.music.load(GAME_BGM_PATH)
            # Apply current volume settings immediately
            pygame.mixer.music.set_volume(settings.music_volume * settings.master_volume)
            pygame.mixer.music.play(-1) # Loop forever
        except Exception as e:
            print(f"Error loading Game BGM: {e}")
    else:
        print(f"Game BGM not found at: {GAME_BGM_PATH}")
    # --- NEW MUSIC LOGIC END ---

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
    
    # Boss fight initialization
    boss_sprites = load_boss_sprites()
    in_boss_room = False
    boss_room = None
    boss = None
    boss_defeated = False
    
    
    # Start on the left, on ground level
    spawn_x = 100
    spawn_y = GROUND_LEVEL - 60
    
    stats_p1 = local_stats if (net_role != ROLE_CLIENT) else None 
    stats_p2 = local_stats if (net_role != ROLE_HOST) else None
    if net_role == ROLE_LOCAL_ONLY:
        stats_p1 = local_stats
        stats_p2 = local_stats

    # Pass sprites to Player Constructor
    p1 = Player(COL_ACCENT_1, spawn_x, spawn_y, stats_p1, sprite_dict=player1_sprites, ability=p1_ability)
    p2 = Player(COL_ACCENT_2, spawn_x - 30, spawn_y, stats_p2, sprite_dict=player2_sprites, ability=p2_ability)
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
    
    view1_surf = pygame.Surface((VIRTUAL_W, VIRTUAL_H // 2))
    view2_surf = pygame.Surface((VIRTUAL_W, VIRTUAL_H // 2))

    distance, elapsed = 0.0, 0.0
    running, game_over = True, False
    winner_text = ""
    p1_distance, p2_distance = 0.0, 0.0
    p1_orbs, p2_orbs = 0, 0
    lb_key = {MODE_SINGLE: "single", MODE_COOP: "coop", MODE_VERSUS: "versus"}[mode]
    screen_shake_timer = 0.0
    session_credits = 0.0
    waiting_for_seed = (net_role == ROLE_CLIENT)
    
    # Tutorial system
    tutorial_active = True
    tutorial_moved = False
    tutorial_linger_timer = 0.0
    tutorial_linger_duration = 3.0

    # === DYNAMIC KEYBIND HELPER ===
    kb = settings.keybinds
    def get_p1_inputs(keys_pressed):
        return (
            keys_pressed[kb["p1_left"]],
            keys_pressed[kb["p1_right"]],
            keys_pressed[kb["p1_jump"]],
            keys_pressed[kb["p1_slam"]]
        )
        
    def get_p2_inputs(keys_pressed):
        return (
            keys_pressed[kb["p2_left"]],
            keys_pressed[kb["p2_right"]],
            keys_pressed[kb["p2_jump"]],
            keys_pressed[kb["p2_slam"]]
        )

    def render_scene(target_surf, cam_x_now, cam_y_now, highlight_player=None):
        # Initialize local drawing coordinates
        draw_cam_x = cam_x_now
        draw_cam_y = cam_y_now

        # 1. DRAW BACKGROUND & ENVIRONMENT
        if in_boss_room and boss_room:
            # FORCE CAMERA TO 0,0 FOR BOSS ROOM
            draw_cam_x = 0
            draw_cam_y = 0
            
            boss_room.draw(target_surf)
            
            # Draw boss
            if boss:
                boss.draw(target_surf)
                
                if boss.alive:
                    # Dimensions
                    bar_total_width = 300
                    bar_height = 20
                    screen_center_x = target_surf.get_width() // 2
                    
                    # Positions
                    start_x = screen_center_x - bar_total_width // 2
                    start_y = 25
                    
                    # 1. Draw Name Label
                    label_surf = font_med.render("NECROMANCER", False, (255, 50, 50)) # Red text
                    target_surf.blit(label_surf, (screen_center_x - label_surf.get_width()//2, start_y - 22))
                    
                    # 2. Draw Background Box (Dark Red)
                    pygame.draw.rect(target_surf, (40, 0, 0), (start_x, start_y, bar_total_width, bar_height))
                    # Border
                    pygame.draw.rect(target_surf, (150, 0, 0), (start_x, start_y, bar_total_width, bar_height), 2)
                    
                    # 3. Draw Segments (Player HP Logic)
                    if boss.max_hp > 0:
                        # Calculate width of one HP chunk
                        segment_width = bar_total_width / boss.max_hp
                        
                        for i in range(boss.hp):
                            # X position for this specific block
                            seg_x = start_x + (i * segment_width)
                            
                            # Width of block (subtract 2 for gap effect)
                            draw_w = segment_width - 2
                            if draw_w < 1: draw_w = 1 # Safety for high HP counts
                            
                            # Draw Red Block
                            # Add slight padding inside (y+2, h-4)
                            pygame.draw.rect(target_surf, (255, 0, 0), (seg_x + 1, start_y + 2, draw_w, bar_height - 4))

        else:
            # Normal Level Draw
            if bg_obj:
                bg_obj.draw(target_surf, draw_cam_x)
            else:
                draw_gradient_background(target_surf, level.current_stage)
            
            if waiting_for_seed:
                txt = font_med.render("SYNCING MAP DATA...", False, COL_ACCENT_1)
                target_surf.blit(txt, txt.get_rect(center=(target_surf.get_width()//2, target_surf.get_height()//2)))
                return

            level.draw(target_surf, draw_cam_x, draw_cam_y)

        # DRAW PARTICLES (Shared)
        for p in particles: p.draw(target_surf, draw_cam_x, draw_cam_y)

        # HELPER: DRAW FLOATING COOLDOWN BARS
        def draw_floating_cd(pl):
            cd_val = 0.0
            max_cd = 1.0
            
            if pl.ability_type == "Slam":
                cd_val = pl.slam_cooldown
                max_cd = pl.slam_cd_val
            elif pl.ability_type == "Dash":
                cd_val = pl.dash_cooldown
                max_cd = pl.dash_cd_val

            # Only draw if cooldown is active
            if cd_val > 0:
                sx = pl.x - draw_cam_x
                sy = pl.y - draw_cam_y
                bar_w = pl.w
                bar_h = 4
                bar_y = sy - 8 
                pygame.draw.rect(target_surf, (0,0,0), (sx, bar_y, bar_w, bar_h))
                ratio = cd_val / max_cd
                fill_w = int(bar_w * ratio)
                pygame.draw.rect(target_surf, (200, 200, 200), (sx, bar_y, fill_w, bar_h))

        # DRAW PLAYERS
        if use_p1 and p1.alive: 
            p1.draw(target_surf, draw_cam_x, draw_cam_y)
            draw_floating_cd(p1)

        if use_p2 and p2.alive: 
            p2.draw(target_surf, draw_cam_x, draw_cam_y)
            draw_floating_cd(p2)

        # DRAW FLOATING TEXT
        for ft in floating_texts: ft.draw(target_surf, draw_cam_x, draw_cam_y)
        
        p1_total = int(p1_distance / 10 + p1_orbs * 100)
        p2_total = int(p2_distance / 10 + p2_orbs * 100)
        
        # In coop mode, combine scores
        if mode == MODE_COOP:
            combined_score = p1_total + p2_total
        
        # HUD Panel (Top Left Stats)
        draw_panel(target_surf, pygame.Rect(5, 5, 120, 50), color=(0, 0, 0, 100))
        target_surf.blit(font_small.render(f"DIST: {int(distance/10)}m", False, COL_TEXT), (10, 10))
        target_surf.blit(font_small.render(f"STAGE: {level.current_stage}", False, COL_TEXT), (10, 28))
        
        hud_y = 65
        
        def draw_player_hud(pl, name, y_pos, is_highlighted, show_score=True):
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

            # PTS (Top Right) - Only show if requested
            if show_score:
                if mode == MODE_COOP:
                    score_val = combined_score
                else:
                    score_val = p1_total if pl == p1 else p2_total
                score_str = f"PTS {score_val}"
                score_surf = font_small.render(score_str, False, COL_ACCENT_3)
                score_x = target_surf.get_width() - score_surf.get_width() - 15
                score_bg_rect = pygame.Rect(score_x - 5, y_pos, score_surf.get_width() + 10, 24)
                draw_panel(target_surf, score_bg_rect, color=(0, 0, 0, 150))
                target_surf.blit(score_surf, (score_x, y_pos + 4))

        if use_p1:
            # In coop mode, show score only on P1's HUD
            draw_player_hud(p1, "P1", hud_y, highlight_player == 1, show_score=True)
            hud_y += 30 
        if use_p2:
            # In coop mode, don't show score on P2's HUD (already shown on P1)
            draw_player_hud(p2, "P2", hud_y, highlight_player == 2, show_score=(mode != MODE_COOP))

    while running:
        # CLAMP DT to prevent physics explosions on first frame or lag spikes
        dt = clock.tick(settings.target_fps) / 1000.0
        dt = min(dt, 0.05) # Max 0.05s per frame (20 FPS min physics speed)

        if not game_over and not waiting_for_seed: elapsed += dt
        
        # Update tutorial state
        if tutorial_active and tutorial_moved:
            tutorial_linger_timer += dt
            if tutorial_linger_timer >= tutorial_linger_duration:
                tutorial_active = False
        
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
                
                # --- BOSS ROOM PORTAL CHECK ---
                if not in_boss_room and level.portal and not game_over:
                    if level.portal.check_collision(local_player.rect()):
                        in_boss_room = True
                        boss_room = BossRoom(tile_surf)
                        boss = NecromancerBoss(boss_sprites, boss_room.width, boss_room.height, boss_room.platforms)
                        
                        # Teleport player to boss room
                        local_player.x = boss_room.width // 2 - local_player.w // 2
                        local_player.y = boss_room.height - 150
                        local_player.vx = 0
                        local_player.vy = 0
                
                # --- BOSS ROOM UPDATE ---
                if in_boss_room and boss_room:
                    boss_room.update(dt)
                    
                    # Update boss - CHANGED: Run update as long as boss object exists
                    # to allow death animation to play out
                    if boss:
                        target_x = local_player.x + local_player.w // 2
                        target_y = local_player.y + local_player.h // 2
                        
                        # boss.update returns True if it hit the player
                        projectile_hit = boss.update(dt, target_x, target_y, local_player.rect())
                        
                        # Only handle interactions if boss is actually alive
                        if boss.alive:
                            # Projectile damage
                            if projectile_hit and local_player.invul_timer <= 0:
                                local_player.take_damage(1)
                            
                            # Check platform fire damage
                            if boss.check_platform_fire_damage(local_player.rect()):
                                if not hasattr(local_player, 'fire_damage_timer'):
                                    local_player.fire_damage_timer = 0
                                local_player.fire_damage_timer -= dt
                                if local_player.fire_damage_timer <= 0:
                                    local_player.take_damage(1)
                                    local_player.fire_damage_timer = 0.5
                            else:
                                if hasattr(local_player, 'fire_damage_timer'):
                                    local_player.fire_damage_timer = 0
                                    
                            # --- BOSS COLLISION LOGIC ---
                            if local_player.rect().colliderect(boss.rect()):
                                # CASE A: Player hits Boss (Only when boss is tired)
                                if boss.state == "TIRED" and (local_player.slam_active or local_player.vy > 100):
                                    died = boss.take_damage(1)
                                    local_player.vy = -350  # Bounce player
                                    
                                    if died:
                                        boss_defeated = True
                                        p1_orbs += 5  # Reward
                                        boss_room.activate_victory()
                                
                                # CASE B: Boss hits Player (Contact Damage)
                                elif boss.state == "ATTACKING" and boss.recovery_timer <= 0:
                                    # Push player away and deal damage
                                    local_player.take_damage(1, source_x=boss.x + boss.w//2)
                    
                    # Collect credits in boss room
                    credits_collected = boss_room.collect_credit(local_player.rect())
                    if credits_collected > 0:
                        session_credits += credits_collected
                        
                    # Check return portal
                    if boss_defeated and boss_room.check_portal_entry(local_player.rect()):
                        in_boss_room = False
                        boss_room = None
                        boss = None
                        boss_defeated = False

                        level.portal = None
                        
                        local_player.x = PORTAL_SPAWN_DISTANCE + 100 
                        local_player.y = GROUND_LEVEL - 100
                        local_player.vx = 0
                        local_player.vy = 0
                
                # --- UPDATE PLAYERS ---
                current_level = boss_room if in_boss_room else level
                
                if mode == MODE_SINGLE or net_role != ROLE_LOCAL_ONLY:
                    # In Network Play (Client or Host) or Single Player:
                    # The local user controls their character using P1 Keybinds (Standard behavior)
                    i_left, i_right, i_jump, i_slam = get_p1_inputs(keys)
                    
                    # Check for first movement for tutorial
                    if tutorial_active and not tutorial_moved and (i_left or i_right or i_jump or i_slam):
                        tutorial_moved = True
                    
                    local_player.update(dt, current_level, i_left, i_right, i_jump, i_slam)
                else:
                    # Local Multiplayer (Same Keyboard): P1 uses P1 keys, P2 uses P2 keys
                    if p1_local and use_p1: 
                        i_left, i_right, i_jump, i_slam = get_p1_inputs(keys)
                        
                        # Check for first movement for tutorial
                        if tutorial_active and not tutorial_moved and (i_left or i_right or i_jump or i_slam):
                            tutorial_moved = True
                        
                        p1.update(dt, current_level, i_left, i_right, i_jump, i_slam)
                    if p2_local and use_p2: 
                        i_left, i_right, i_jump, i_slam = get_p2_inputs(keys)
                        
                        # Check for first movement for tutorial (p2 can also trigger it)
                        if tutorial_active and not tutorial_moved and (i_left or i_right or i_jump or i_slam):
                            tutorial_moved = True
                        
                        p2.update(dt, current_level, i_left, i_right, i_jump, i_slam)

                # --- CAMERA UPDATE (HORIZONTAL) ---
                if mode == MODE_VERSUS and net_role == ROLE_LOCAL_ONLY and use_p1 and use_p2:
                    # Split screen cam logic
                    tx1 = p1.x if p1.alive else (p2.x if p2.alive else p1.x)
                    tx2 = p2.x if p2.alive else (p1.x if p1.alive else p2.x)
                    
                    ty1 = p1.y if p1.alive else (p2.y if p2.alive else p1.y)
                    ty2 = p2.y if p2.alive else (p1.y if p1.alive else p2.y)

                    target_cam_y1 = ty1 - (VIRTUAL_H // 4)
                    target_cam_y2 = ty2 - (VIRTUAL_H // 4)

                    cam_x_p1 += ((tx1 - 200) - cam_x_p1) * 0.1
                    cam_x_p2 += ((tx2 - 200) - cam_x_p2) * 0.1
                    
                    cam_y_p1 += (target_cam_y1 - cam_y_p1) * 0.1
                    cam_y_p2 += (target_cam_y2 - cam_y_p2) * 0.1

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

                for horb in level.health_orbs[:]:
                    # P1 check
                    if use_p1 and p1.alive and p1.rect().colliderect(horb): 
                        if p1.hp < p1.max_hp:
                            p1.hp += 1
                            floating_texts.append(FloatingText(horb.x, horb.y, "+1 HP", font_small, (50, 255, 50)))
                        else:
                            # If full HP, just give a small score bonus or "MAX" text
                            floating_texts.append(FloatingText(horb.x, horb.y, "MAX HP", font_small, (200, 255, 200)))
                        level.health_orbs.remove(horb)
                        continue
                    
                    # P2 check
                    if use_p2 and p2.alive and p2.rect().colliderect(horb): 
                        if p2.hp < p2.max_hp:
                            p2.hp += 1
                            floating_texts.append(FloatingText(horb.x, horb.y, "+1 HP", font_small, (50, 255, 50)))
                        else:
                            floating_texts.append(FloatingText(horb.x, horb.y, "MAX HP", font_small, (200, 255, 200)))
                        level.health_orbs.remove(horb)
                # ==========================================

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
                            player.dash_active = False
                        return
                    
                    r = player.rect()
                    # Obstacle Collisions
                    for obs in level.obstacles: 
                        if r.colliderect(obs): 
                            if player.dash_active: continue # Phase through spikes
                            player.take_damage(1, source_x=obs.centerx) 
                            return
                    
                    # Enemy Collisions
                    for e in level.enemies: 
                        if r.colliderect(e.rect()): 
                            if player.dash_active: continue # Phase through enemies
                            
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
                
                # Combined score for coop mode
                combined_score = p1_total + p2_total if mode == MODE_COOP else 0
                
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
                        finish("Team", combined_score, "MISSION FAILED")
                elif mode == MODE_VERSUS and not p1.alive and not p2.alive:
                        winner = "DRAW" if p1_total == p2_total else ("P1 WINS" if p1_total > p2_total else "P2 WINS")
                        finish(winner, max(p1_total, p2_total), winner)

        canvas.fill(COL_BG)
        final_cam_x = cam_x + shake_x
        final_cam_y = cam_y + shake_y

        if mode == MODE_VERSUS and net_role == ROLE_LOCAL_ONLY and use_p1 and use_p2:
            render_scene(view1_surf, cam_x_p1, cam_y_p1, highlight_player=1)
            render_scene(view2_surf, cam_x_p2, cam_y_p2, highlight_player=2)
            half_h = VIRTUAL_H // 2
            canvas.blit(view1_surf, (0, 0))
            canvas.blit(view2_surf, (0, half_h))
            pygame.draw.line(canvas, COL_UI_BORDER, (0, half_h), (VIRTUAL_W, half_h), 4)
        else:
            render_scene(canvas, final_cam_x, final_cam_y, highlight_player=None)
        
        # Draw tutorial overlay
        if tutorial_active and not waiting_for_seed and net_role == ROLE_LOCAL_ONLY:
            # Semi-transparent overlay
            overlay = pygame.Surface((VIRTUAL_W, VIRTUAL_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            canvas.blit(overlay, (0, 0))
            
            # Get P1 key names
            p1_left_key = pygame.key.name(kb["p1_left"]).upper()
            p1_right_key = pygame.key.name(kb["p1_right"]).upper()
            p1_jump_key = pygame.key.name(kb["p1_jump"]).upper()
            p1_ability_key = pygame.key.name(kb["p1_slam"]).upper()
            
            # Get P2 key names
            p2_left_key = pygame.key.name(kb["p2_left"]).upper()
            p2_right_key = pygame.key.name(kb["p2_right"]).upper()
            p2_jump_key = pygame.key.name(kb["p2_jump"]).upper()
            p2_ability_key = pygame.key.name(kb["p2_slam"]).upper()
            
            line_spacing = 35
            
            if mode == MODE_VERSUS and use_p1 and use_p2:
                # Split screen vertical - P1 top half, P2 bottom half
                half_h = VIRTUAL_H // 2
                
                # P1 Tutorial (Top half)
                y_center_p1 = half_h // 2
                move_text = f"[{p1_left_key}] [{p1_right_key}] to move"
                draw_text_shadow(canvas, font_small, move_text, VIRTUAL_W//2, y_center_p1 - line_spacing, center=True, col=COL_ACCENT_1)
                jump_text = f"[{p1_jump_key}] to jump"
                draw_text_shadow(canvas, font_small, jump_text, VIRTUAL_W//2, y_center_p1, center=True, col=COL_ACCENT_1)
                ability_text = f"[{p1_ability_key}] for ability!"
                draw_text_shadow(canvas, font_small, ability_text, VIRTUAL_W//2, y_center_p1 + line_spacing, center=True, col=COL_ACCENT_3)
                
                # P2 Tutorial (Bottom half)
                y_center_p2 = half_h + half_h // 2
                move_text = f"[{p2_left_key}] [{p2_right_key}] to move"
                draw_text_shadow(canvas, font_small, move_text, VIRTUAL_W//2, y_center_p2 - line_spacing, center=True, col=COL_ACCENT_2)
                jump_text = f"[{p2_jump_key}] to jump"
                draw_text_shadow(canvas, font_small, jump_text, VIRTUAL_W//2, y_center_p2, center=True, col=COL_ACCENT_2)
                ability_text = f"[{p2_ability_key}] for ability!"
                draw_text_shadow(canvas, font_small, ability_text, VIRTUAL_W//2, y_center_p2 + line_spacing, center=True, col=COL_ACCENT_3)
                
            elif mode == MODE_COOP and use_p1 and use_p2:
                # Coop - P1 on left, P2 on right
                y_center = VIRTUAL_H // 2
                quarter_w = VIRTUAL_W // 4
                
                # P1 Tutorial (Left side)
                draw_text_shadow(canvas, font_small, "PLAYER 1", quarter_w, y_center - line_spacing * 2, center=True, col=COL_ACCENT_1)
                move_text = f"[{p1_left_key}] [{p1_right_key}] move"
                draw_text_shadow(canvas, font_small, move_text, quarter_w, y_center - line_spacing, center=True, col=COL_ACCENT_1)
                jump_text = f"[{p1_jump_key}] jump"
                draw_text_shadow(canvas, font_small, jump_text, quarter_w, y_center, center=True, col=COL_ACCENT_1)
                ability_text = f"[{p1_ability_key}] ability"
                draw_text_shadow(canvas, font_small, ability_text, quarter_w, y_center + line_spacing, center=True, col=COL_ACCENT_3)
                
                # P2 Tutorial (Right side)
                draw_text_shadow(canvas, font_small, "PLAYER 2", quarter_w * 3, y_center - line_spacing * 2, center=True, col=COL_ACCENT_2)
                move_text = f"[{p2_left_key}] [{p2_right_key}] move"
                draw_text_shadow(canvas, font_small, move_text, quarter_w * 3, y_center - line_spacing, center=True, col=COL_ACCENT_2)
                jump_text = f"[{p2_jump_key}] jump"
                draw_text_shadow(canvas, font_small, jump_text, quarter_w * 3, y_center, center=True, col=COL_ACCENT_2)
                ability_text = f"[{p2_ability_key}] ability"
                draw_text_shadow(canvas, font_small, ability_text, quarter_w * 3, y_center + line_spacing, center=True, col=COL_ACCENT_3)
                
            else:
                # Single player or network - just show P1 controls
                y_center = VIRTUAL_H // 2
                line_spacing = 45
                
                move_text = f"Press [{p1_left_key}] and [{p1_right_key}] to move left and right"
                draw_text_shadow(canvas, font_med, move_text, VIRTUAL_W//2, y_center - line_spacing, center=True, col=COL_ACCENT_1)
                
                jump_text = f"Press [{p1_jump_key}] to jump"
                draw_text_shadow(canvas, font_med, jump_text, VIRTUAL_W//2, y_center, center=True, col=COL_ACCENT_1)
                
                ability_text = f"Press [{p1_ability_key}] to use your ability!"
                draw_text_shadow(canvas, font_med, ability_text, VIRTUAL_W//2, y_center + line_spacing, center=True, col=COL_ACCENT_3)

        if game_over:
            overlay = pygame.Surface((VIRTUAL_W, VIRTUAL_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            canvas.blit(overlay, (0, 0))
            
            draw_text_shadow(canvas, font_big, winner_text, VIRTUAL_W//2, VIRTUAL_H//2 - 40, center=True, col=COL_ACCENT_3)
            draw_text_shadow(canvas, font_med, f"CREDITS EARNED: {int(session_credits)}", VIRTUAL_W//2, VIRTUAL_H//2, center=True)
            draw_text_shadow(canvas, font_small, "[ESC] Return to Menu", VIRTUAL_W//2, VIRTUAL_H//2 + 30, center=True)
            
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