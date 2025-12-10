"""
Player class - the main playable character.
"""
import random
import pygame

from config.constants import (
    TILE_SIZE, BASE_PLAYER_SPEED, BASE_JUMP_VEL, BASE_GRAVITY,
    BASE_SLAM_COOLDOWN, BASE_DASH_COOLDOWN, BASE_SLAM_SPEED,
    BASE_DASH_SPEED, BASE_DASH_DURATION, WALL_SLIDE_SPEED,
    WALL_JUMP_X, WALL_JUMP_Y, COL_ACCENT_1, COL_ACCENT_2
)
from core.helpers import lerp
from effects.particles import spawn_dust, spawn_slam_impact


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
        self.anim_speed = 0.1  # Default

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
        self.idle_state = "main"  # "main", "alt1", "alt2"
        self.idle_alt_trigger_count = random.randint(7, 12)
        self.idle_main_loop_counter = 0
        
        # Update collider size based on first sprite if available
        if self.sprites and "idle_main" in self.sprites and self.sprites["idle_main"]:
            ref_surf = self.sprites["idle_main"][0]
            self.w = ref_surf.get_width()
            self.h = ref_surf.get_height()
        else:
            self.w = 20
            self.h = 20

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), int(self.w), int(self.h))

    def update(self, dt, level, input_left, input_right, input_jump, input_slam):
        if not self.alive: return

        if self.slam_active or self.dash_active:
             self.trail.append([self.x, self.y, 200])

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
        if self.knockback_timer > 0:
            self.knockback_timer -= dt
            input_left = False
            input_right = False
            input_jump = False
            input_slam = False
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
        
        if not self.is_dying and self.knockback_timer <= 0 and not self.dash_active: 
            if input_left: 
                desired_vx -= self.speed_val
                self.facing_right = False
            if input_right: 
                desired_vx += self.speed_val
                self.facing_right = True

        if self.on_ground: 
            if self.knockback_timer > 0:
                self.vx = lerp(self.vx, 0, dt * 5)
            elif not self.dash_active:
                self.vx = 0 if self.is_dying else desired_vx
        else: 
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
                
                dash_dir = 1 if self.facing_right else -1
                if input_left: dash_dir = -1
                if input_right: dash_dir = 1
                self.facing_right = (dash_dir == 1)
                
                self.vx = dash_dir * self.dash_speed
                self.vy = 0
                spawn_dust(self.x + self.w/2, self.y + self.h/2, count=8, color=COL_ACCENT_2)

        # Update Dash State
        if self.dash_active:
            self.dash_timer -= dt
            self.vy = 0
            dash_dir = 1 if self.facing_right else -1
            self.vx = dash_dir * self.dash_speed
            
            if self.dash_timer <= 0:
                self.dash_active = False
                self.vx *= 0.5
                
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
            new_action = "slam" 
        elif self.knockback_timer > 0:
             new_action = "hit"
        else:
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
            
            if prev_action == "fall" and new_action == "land":
                self.frame_index = 9
            elif prev_action == "jump" and new_action == "fall" and self.jump_frames:
                world_idx = prev_frame
                world_idx = max(self.fall_start_idx, min(self.fall_end_idx, world_idx))
                self.frame_index = world_idx - self.fall_start_idx
            else:
                self.frame_index = 0

            self.current_action = new_action
            if new_action != "idle": self.idle_state = "main" 

        # PER-ACTION ANIMATION
        if not self.sprites: return

        if self.current_action == "land":
            self.frame_index = 9
            return

        if self.current_action == "slam":
            frames = self.slam_frames
            if frames:
                speed = 0.06
                if self.anim_timer > speed:
                    if self.frame_index < len(frames) - 1:
                        self.frame_index += 1
                    self.anim_timer = 0.0
            return 

        if self.current_action == "fall" and self.jump_frames:
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
        if self.invul_timer > 0 or self.slam_active or self.is_dying or not self.alive or self.dash_active:
            return
        
        self.hp -= amount
        
        self.invul_timer = 1.2 
        self.flash_on_invul = True
        self.knockback_timer = 0.3 
        self.current_action = "hit" 
        
        self.vy = -350 
        self.on_ground = False
        
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
            c = self.color
            if self.dash_active: c = COL_ACCENT_2 
            
            s.fill(c)
            s.set_alpha(int(t[2] * 0.5))
            surf.blit(s, rect)

        if self.invul_timer > 0 and self.flash_on_invul:
            if int(self.invul_timer * 15) % 2 != 0:
                return

        if self.sprites:
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
            
            phys_center_x = self.x + self.w / 2
            phys_bottom = self.y + self.h
            
            sprite_draw_x = phys_center_x - img.get_width() / 2 - cam_x
            sprite_draw_y = phys_bottom - img.get_height() - cam_y
            
            surf.blit(img, (sprite_draw_x, sprite_draw_y))
        else:
            draw_x = self.x - cam_x
            draw_y = self.y - cam_y
            pygame.draw.rect(surf, self.color, (draw_x, draw_y, self.w, self.h))

        if self.slam_active:
            cx = (self.x - cam_x) + self.w / 2
            top_y = (self.y - cam_y)
            pygame.draw.line(surf, (255, 255, 255), (cx, top_y), (cx, top_y - 40), 2)
            pygame.draw.line(surf, (255, 255, 255), (cx - 10, top_y + 10), (cx - 10, top_y - 20), 1)
            pygame.draw.line(surf, (255, 255, 255), (cx + 10, top_y + 10), (cx + 10, top_y - 20), 1)

        if self.shockwave_timer > 0:
            max_rad = 100
            progress = 1.0 - (self.shockwave_timer / 0.3)
            rad = int(max_rad * progress)
            
            cx = int((self.x - cam_x) + self.w / 2)
            cy = int((self.y - cam_y) + self.h) 
            
            pygame.draw.circle(surf, (200, 255, 255), (cx, cy), rad, 2)
