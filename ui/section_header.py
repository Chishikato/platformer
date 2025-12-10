"""
SectionHeader UI widget.
"""
import pygame

from config.constants import COL_ACCENT_1
from core.helpers import draw_text_shadow


class SectionHeader:
    def __init__(self, x, y, text, font, color=COL_ACCENT_1):
        self.text = text
        self.font = font
        self.color = color
        # Create a rect for layout calculation, though we won't click it
        text_surf = font.render(text, True, color)
        self.rect = text_surf.get_rect(center=(x, y))
        # Add padding for visual spacing
        self.rect.height += 20 

    def handle_event(self, event):
        pass  # Headers ignore events, preventing the crash

    def draw(self, surf):
        # Draw a cool underline
        line_y = self.rect.centery + 10
        center_x = self.rect.centerx
        
        # Draw text with shadow
        draw_text_shadow(surf, self.font, self.text, center_x, self.rect.centery - 5, 
                         center=True, col=self.color)
        
        # Neon line fading out to sides
        width = 200
        pygame.draw.line(surf, self.color, (center_x - width//2, line_y), (center_x + width//2, line_y), 2)
