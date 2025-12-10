"""
Particle and floating text visual effects.
"""
import random
import math
import pygame

from config.constants import COL_ACCENT_2, COL_ACCENT_3, COL_ACCENT_1


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


# Global particle lists
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
