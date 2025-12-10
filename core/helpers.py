"""
Helper/utility functions used throughout the game.
"""
import math
import pygame

from config.constants import COL_TEXT, COL_SHADOW, COL_ACCENT_1, COL_UI_BG, COL_UI_BORDER


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def lerp(start, end, t):
    return start + t * (end - start)


def draw_text_shadow(surf, font, text, x, y, col=COL_TEXT, shadow_col=COL_SHADOW,
                     center=False, pulse=False, time_val=0):
    offset_y = 0

    if pulse:
        # Slight bobbing
        offset_y = math.sin(time_val * 4) * 3

        # Base cyan from your palette
        base_r, base_g, base_b = COL_ACCENT_1  # (0, 234, 255)

        # Pulse brightness between ~60% and 100%
        bright = 0.6 + 0.4 * math.sin(time_val * 5)
        if bright < 0.0:
            bright = 0.0

        r = int(base_r * bright)
        g = int(base_g * bright)
        b = int(base_b * bright)
        col = (r, g, b)

        # Darker cyan for the shadow
        shadow_col = (r // 4, g // 4, b // 4)

    # Base text surfaces
    shad = font.render(text, False, shadow_col)
    fore = font.render(text, False, col)

    final_y = y + offset_y

    if center:
        rect = fore.get_rect(center=(x, final_y))

        if pulse:
            # Cyan glow: soft copies around the text
            glow = font.render(text, False, col)
            glow.set_alpha(90)
            for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2)]:
                surf.blit(glow, (rect.x + dx, rect.y + dy))

        surf.blit(shad, (rect.x + 2, rect.y + 2))
        surf.blit(fore, rect)
        return rect
    else:
        base_x, base_y = x, final_y

        if pulse:
            # Cyan glow: soft copies around the text
            glow = font.render(text, False, col)
            glow.set_alpha(90)
            for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2)]:
                surf.blit(glow, (base_x + dx, base_y + dy))

        surf.blit(shad, (base_x + 2, base_y + 2))
        surf.blit(fore, (base_x, base_y))
        return pygame.Rect(base_x, base_y, fore.get_width(), fore.get_height())


def draw_panel(surf, rect, color=COL_UI_BG, border=COL_UI_BORDER):
    pygame.draw.rect(surf, COL_SHADOW, (rect.x + 4, rect.y + 4, rect.w, rect.h), border_radius=6)
    pygame.draw.rect(surf, color, rect, border_radius=6)
    pygame.draw.rect(surf, border, rect, 2, border_radius=6)
