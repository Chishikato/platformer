"""
Slider UI widget.
"""
import pygame

from config.constants import COL_TEXT, COL_ACCENT_1, COL_ACCENT_3
from core.helpers import clamp, draw_panel


class Slider:
    def __init__(self, rect, label, font, get_value, set_value, min_v=0.0, max_v=1.0):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.font = font
        self.get_value = get_value
        self.set_value = set_value
        self.min_v, self.max_v = min_v, max_v
        self.dragging = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.dragging = True
                self._update_from_mouse(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._update_from_mouse(event.pos[0])

    def _update_from_mouse(self, mx):
        x0, x1 = self.rect.x + 10, self.rect.right - 10
        t = clamp((mx - x0) / (x1 - x0), 0.0, 1.0)
        self.set_value(self.min_v + t * (self.max_v - self.min_v))

    def draw(self, surf):
        draw_panel(surf, self.rect)
        label_s = self.font.render(self.label, False, COL_TEXT)
        surf.blit(label_s, (self.rect.x + 10, self.rect.y + 5))
        line_y = self.rect.bottom - 15
        x0, x1 = self.rect.x + 10, self.rect.right - 10
        pygame.draw.line(surf, (100, 100, 120), (x0, line_y), (x1, line_y), 4)
        v = clamp(self.get_value(), self.min_v, self.max_v)
        t = (v - self.min_v) / (self.max_v - self.min_v + 1e-6)
        knob_x = x0 + t * (x1 - x0)
        pygame.draw.circle(surf, COL_ACCENT_1, (int(knob_x), line_y), 8)
        val_str = f"{int(v)}" if self.max_v > 2 else f"{v:.2f}"
        val_s = self.font.render(val_str, False, COL_ACCENT_3)
        surf.blit(val_s, (self.rect.right - val_s.get_width() - 10, self.rect.y + 5))
