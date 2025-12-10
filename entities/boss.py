"""
NecromancerBoss class - main boss enemy with attack patterns and vulnerability cycles.
"""
import random
import math
import pygame

from config.constants import (
    BOSS_HP, BOSS_FLIGHT_HEIGHT, BOSS_TIRED_HEIGHT,
    ATTACK_DURATION_MIN, ATTACK_DURATION_MAX, TIRED_DURATION,
    ENRAGE_ATTACK_SPEED_MULTIPLIER
)


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

    def reset_projectiles(self):
        """Clears all active attacks (useful when room resets)"""
        self.projectiles.clear()
        self.platform_fires.clear()
        
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
    
    def update_visuals_only(self, dt):
        # Update projectile movement (visual only)
        for proj in self.projectiles[:]:
            proj["x"] += proj["vx"] * dt
            proj["y"] += proj["vy"] * dt
            proj["lifetime"] -= dt
            if (proj["lifetime"] <= 0 or 
                proj["x"] < -50 or proj["x"] > self.room_width + 50 or 
                proj["y"] < -50 or proj["y"] > self.room_height + 50):
                self.projectiles.remove(proj)
        
        # Update fire visuals
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

        # Update body animation
        self._update_animation(dt)
        self.invul_timer -= dt
        
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
