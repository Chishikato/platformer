"""
Parallax background and gradient drawing.
"""
import os
import math
import pygame

from config.constants import get_asset_path


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
