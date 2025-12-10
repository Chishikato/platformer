"""
Enemy class - patrolling enemies that can damage the player.
"""
import pygame

from config.constants import BASE_GRAVITY


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
        self.facing_right = True  # Track direction for flipping sprites
        
        self.is_boss = is_boss 
        self.max_hp = hp
        self.hp = self.max_hp
        self.invul_timer = 0.0 
        
        self.alive = True
        self.anim_timer = 0.0
        self.frame_index = 0
        self.current_action = "walk"
        
        # Network ID for multiplayer sync
        self.id = -1

    def rect(self): 
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def take_damage(self, amount):
        if self.invul_timer > 0: return False
        
        self.hp -= amount
        self.invul_timer = 0.2  # Short invulnerability
        self.current_action = "hurt"  # Switch to hurt animation
        self.frame_index = 0  # Reset frame for the hit reaction
        
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            return True
        return False

    def update_animation(self, dt):
        if not self.alive: return

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

    def update(self, dt, players, level, cam_rect):
        if not self.alive: return False
        
        self.update_animation(dt)
        if self.vx > 0: self.facing_right = True
        elif self.vx < 0: self.facing_right = False

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
        my_hitbox = self.rect()
        for obs in level.obstacles:
            if my_hitbox.colliderect(obs):
                died = self.take_damage(10.0) 
                if died: return True 

        return False 

    def draw(self, surf, cam_x, cam_y):
        if not self.alive: return
        
        draw_x = self.x - cam_x
        draw_y = self.y - cam_y
        
        # Retrieve frames
        frames = self.sprites.get(self.current_action, self.sprites.get("walk", []))
        if not frames:
            # Fallback: draw red rectangle if sprites missing
            pygame.draw.rect(surf, (255, 0, 0), (draw_x, draw_y, self.w, self.h))
            return

        # Loop animation
        img = frames[self.frame_index % len(frames)]

        # Flip if moving right
        if self.facing_right:
            img = pygame.transform.flip(img, True, False)

        # Visual Flash effect when hurt
        if self.current_action == "hurt":
            if int(self.invul_timer * 20) % 2 == 0:
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
