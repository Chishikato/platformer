"""
KeybindButton UI widget.
"""
import math
import pygame

from config.constants import COL_ACCENT_1, COL_ACCENT_2, COL_UI_BG


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
                return True  # Event Consumed

        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.listening = True
                return True  # Consume click
        return False

    def draw(self, surf):
        # Logic for colors based on state
        if self.listening:
            # PULSING PINK GLOW
            pulse = (math.sin(pygame.time.get_ticks() / 150) + 1) * 0.5  # 0.0 to 1.0
            border_col = COL_ACCENT_2  # Hot Pink
            # Interpolate background brightness
            bg_base = 40
            bg_add = int(40 * pulse)
            bg_col = (bg_base + bg_add, 20, 40)  # Reddish tint
            text_col = (255, 200, 200)
            key_str = "DELETE TO CANCEL"
        else:
            # STANDARD / HOVER STATE
            if self.hover:
                border_col = COL_ACCENT_1  # Cyan
                bg_col = (30, 30, 50)
                text_col = (255, 255, 255)
            else:
                border_col = (60, 60, 80)  # Dark Blue/Grey
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
        key_surf = self.font.render(key_str, True, border_col)  # Key takes the accent color
        
        # Add a background pill for the key text for contrast
        key_bg_rect = key_surf.get_rect(midright=(self.rect.right - 15, self.rect.centery))
        key_bg_rect.inflate_ip(20, 10)  # Add padding
        
        # Draw key pill background
        pygame.draw.rect(surf, (10, 10, 15), key_bg_rect, border_radius=4)
        if self.listening:
             pygame.draw.rect(surf, border_col, key_bg_rect, 1, border_radius=4)

        # Blit text centered on the pill
        key_rect = key_surf.get_rect(center=key_bg_rect.center)
        surf.blit(key_surf, key_rect)
