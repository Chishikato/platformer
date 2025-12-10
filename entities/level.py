"""
LevelManager class - procedural level generation and management.
"""
import random
import math
import pygame

from config.constants import (
    TILE_SIZE, VIRTUAL_W, VIRTUAL_H, GROUND_LEVEL,
    STAGE_1_END, STAGE_2_END, PORTAL_SPAWN_DISTANCE, COL_ACCENT_3
)
from effects.credit import Credit
from boss_room.portal import Portal
from .enemy import Enemy


class LevelManager:
    def __init__(self, tile_surface, enemy_sprite_dict, seed, is_client=False):
        self.rng = random.Random(seed)
        self.tile_surf = tile_surface
        self.enemy_sprites = enemy_sprite_dict
        self.is_client = is_client  # Client doesn't generate terrain
        self.platform_segments = []
        self.enemies = []
        self.obstacles = []
        self.orbs = []
        self.health_orbs = []
        self.dropped_credits = []
        
        # Persistent enemy ID counter (never resets, guarantees unique IDs)
        self.next_enemy_id = 0
        
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
        
        # Boss portal
        self.portal = None
        self.portal_spawned = False
        # Store safe coordinates for return trip
        self.return_safe_pos = (100, GROUND_LEVEL - 60)

    def update_client_animations(self, dt):
        for e in self.enemies:
            if e.alive:
                e.update_animation(dt)

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
            self.current_stage = 3  # Endless

        # --- PORTAL SPAWN CHECK ---
        is_portal_segment = False
        if not self.portal_spawned and self.generated_right_x >= PORTAL_SPAWN_DISTANCE:
            is_portal_segment = True

        # --- Height & Gap Calculation ---
        if is_portal_segment:
            delta_tiles = 0
            new_y = self.last_platform_y
            
            base_gap = 40
            plat_w = TILE_SIZE * 20
        else:
            min_change, max_change = 0, 0
            if self.current_stage == 1:
                min_change, max_change = -2, 2
            elif self.current_stage == 2:
                min_change, max_change = -4, 5
            else:
                min_change, max_change = -4, 8

            delta_tiles = self.rng.randint(min_change, max_change)
            new_y = self.last_platform_y + (delta_tiles * TILE_SIZE)

            # Clamp Y
            min_allowed_y = TILE_SIZE * 4
            max_allowed_y = VIRTUAL_H - TILE_SIZE * 2
            if new_y < min_allowed_y: new_y = min_allowed_y + TILE_SIZE
            elif new_y > max_allowed_y: new_y = max_allowed_y - TILE_SIZE

            # Gap logic
            base_gap = 60
            gap_variance = self.rng.randint(0, 40)
            height_diff = self.last_platform_y - new_y
            
            if height_diff > 0:  # Going Up
                penalty = (height_diff / TILE_SIZE) * 12
                final_gap = max(40, (base_gap + gap_variance) - penalty)
            else:  # Going Down
                bonus = (abs(height_diff) / TILE_SIZE) * 8
                final_gap = min(base_gap + gap_variance + bonus, 150)
            
            base_gap = final_gap
            plat_w = TILE_SIZE * self.rng.randint(4, 12)

        # Calculate X position
        new_x = self.generated_right_x + int(base_gap)

        # Add the segment
        self._add_segment(new_x, plat_w, new_y)
        
        # Update trackers
        self.generated_right_x = new_x + plat_w
        self.last_platform_y = new_y
        self.gen_count += 1

        # --- SPAWN ENTITIES ---
        
        if is_portal_segment:
            portal_x = new_x + plat_w // 2 - 30
            portal_y = new_y - 100 
            self.portal = Portal(portal_x, portal_y)
            self.portal_spawned = True
            
            self.return_safe_pos = (portal_x + 100, new_y)
            return

        # Normal Spawning Logic (Enemies, Spikes, Orbs)
        enemy_chance = 0.3
        if self.current_stage == 2: enemy_chance = 0.5
        if self.current_stage == 3: enemy_chance = 0.7
        
        ref_width, ref_height = 32, 32
        if "walk" in self.enemy_sprites and self.enemy_sprites["walk"]:
            ref_surf = self.enemy_sprites["walk"][0]
            ref_width, ref_height = ref_surf.get_width(), ref_surf.get_height()

        if self.rng.random() < enemy_chance and plat_w > TILE_SIZE * 6:
            ex = new_x + plat_w // 2 - ref_width // 2
            ey = new_y - ref_height
            if not self.is_client:
                new_enemy = Enemy(self.enemy_sprites, ex, ey)
                new_enemy.id = self.next_enemy_id
                self.next_enemy_id += 1
                self.enemies.append(new_enemy)
        
        if self.rng.random() < 0.25 and self.current_stage > 1 and plat_w > TILE_SIZE * 6:
            spike_x = new_x + self.rng.randint(3, (plat_w // TILE_SIZE) - 3) * TILE_SIZE
            self.obstacles.append(pygame.Rect(spike_x, new_y - TILE_SIZE, TILE_SIZE, TILE_SIZE))

        if self.rng.random() < 0.5:
             orb_size = TILE_SIZE // 2
             ox = new_x + plat_w // 2 - orb_size // 2
             rect = pygame.Rect(ox, new_y - 3 * TILE_SIZE, orb_size, orb_size)
             if self.rng.random() < 0.08: 
                 self.health_orbs.append(rect)
             else:
                 self.orbs.append(rect)

    def spawn_credit(self, x, y, value):
        self.dropped_credits.append(Credit(x, y, value))

    def update(self, dt, cam_x, difficulty):
        self.orb_timer += dt
        
        target_right = cam_x + VIRTUAL_W + 400
        while self.generated_right_x < target_right:
            self._generate_section()
            
        # Cleanup behind camera (Left side)
        cleanup_x = cam_x - 200
        
        self.platform_segments = [s for s in self.platform_segments if s.right > cleanup_x]
        self.obstacles = [o for o in self.obstacles if o.right > cleanup_x]
        self.orbs = [o for o in self.orbs if o.right > cleanup_x]
        self.health_orbs = [h for h in self.health_orbs if h.right > cleanup_x]
        self.enemies = [e for e in self.enemies if e.alive and e.x > cleanup_x]
        
        for c in self.dropped_credits: c.update(dt, self)
        self.dropped_credits = [c for c in self.dropped_credits if c.life > 0 and c.x > cleanup_x]
        
        # Update portal animation
        if self.portal:
            self.portal.update(dt)

    def update_enemies(self, dt, players, cam_rect, is_client=False):
        """
        Updates enemies and returns TWO lists:
        1. spike_deaths: (x, y) tuples for spawning credits
        2. recently_dead: actual Enemy objects that died this frame (for network sync)
        """
        spike_deaths = []
        recently_dead = []
        
        for e in self.enemies:
            was_alive = e.alive
            
            if is_client:
                if e.y > cam_rect.bottom + 500: e.alive = False
                if e.x < cam_rect.left - 200: e.alive = False
            else:
                if e.update(dt, players, self, cam_rect): 
                    spike_deaths.append((e.x, e.y))
            
            if was_alive and not e.alive:
                recently_dead.append(e)
        
        self.enemies = [e for e in self.enemies if e.alive]
        
        return spike_deaths, recently_dead

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
            pygame.draw.circle(surf, (50, 255, 50), (cx, cy), horb.w // 2)
            pygame.draw.circle(surf, (255, 255, 255), (cx, cy), horb.w // 2 + 2, 1)
            cr_sz = 3
            pygame.draw.rect(surf, (255, 255, 255), (cx - 1, cy - cr_sz, 2, cr_sz*2))
            pygame.draw.rect(surf, (255, 255, 255), (cx - cr_sz, cy - 1, cr_sz*2, 2))

        for c in self.dropped_credits: c.draw(surf, cam_x, cam_y)
        for e in self.enemies: e.draw(surf, cam_x, cam_y)
        
        # Draw boss portal
        if self.portal:
            self.portal.draw(surf, cam_x, cam_y)
