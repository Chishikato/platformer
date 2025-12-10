"""
TextInput UI widget.
"""
import pygame

from config.constants import COL_TEXT, COL_ACCENT_1, COL_UI_BORDER


class TextInput:
    def __init__(self, rect, font, initial_text="", placeholder="", on_enter=None):
        self.rect = pygame.Rect(rect)
        self.font = font
        self.text = initial_text
        self.placeholder = placeholder
        self.on_enter = on_enter
        self.active = False
        self.cursor_timer = 0.0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                self.active = False
                if self.on_enter: self.on_enter(self.text)
            elif event.key == pygame.K_BACKSPACE: self.text = self.text[:-1]
            elif event.key == pygame.K_v and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                self.paste_text()
            else:
                if len(self.text) < 32 and event.unicode.isprintable(): self.text += event.unicode

    def paste_text(self):
        try:
            if hasattr(pygame.scrap, "get_text"):
                decoded = pygame.scrap.get_text()
            else:
                decoded = pygame.scrap.get(pygame.SCRAP_TEXT).decode("utf-8").strip("\x00")
            if decoded and len(self.text) + len(decoded) < 32:
                self.text += decoded
        except: pass

    def update(self, dt):
        self.cursor_timer += dt

    def draw(self, surf):
        border = COL_ACCENT_1 if self.active else COL_UI_BORDER
        pygame.draw.rect(surf, (10, 10, 15), self.rect, border_radius=4)
        pygame.draw.rect(surf, border, self.rect, 2, border_radius=4)
        prev_clip = surf.get_clip()
        surf.set_clip(self.rect.inflate(-4, -4))
        
        display_text = self.text
        text_col = COL_TEXT
        if not self.text and self.placeholder and not self.active:
            display_text = self.placeholder
            text_col = (100, 100, 100)
            
        txt_s = self.font.render(display_text, False, text_col)
        surf.blit(txt_s, (self.rect.x + 6, self.rect.centery - txt_s.get_height()//2))
        
        if self.active and (int(self.cursor_timer * 2) % 2 == 0):
            text_w = self.font.size(self.text)[0] if self.text else 0
            cx = self.rect.x + 6 + text_w + 2
            if cx < self.rect.right - 4:
                pygame.draw.line(surf, COL_TEXT, (cx, self.rect.y + 4), (cx, self.rect.bottom - 4), 2)
        surf.set_clip(prev_clip)
