"""
Credit collectible visual effect.
"""
import random
import math
import pygame

from config.constants import BASE_GRAVITY, COL_ACCENT_3


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
