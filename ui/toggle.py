"""
Toggle UI widget.
"""
import pygame

from config.constants import COL_TEXT, COL_ACCENT_1, COL_ACCENT_3, COL_UI_BORDER
from core.helpers import draw_panel


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
