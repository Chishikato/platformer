"""
Button UI widget.
"""
import math
import pygame

from config.constants import COL_UI_BG, COL_ACCENT_1, COL_SHADOW, COL_UI_BORDER, COL_TEXT


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
