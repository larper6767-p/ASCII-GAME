"""Character-grid renderer with a per-(glyph, colour) surface cache."""
import pygame

from . import config


class Renderer:
    def __init__(self, cols=config.COLS, rows=config.ROWS):
        self.font = pygame.font.SysFont(
            config.FONT_NAME, config.FONT_SIZE, bold=config.FONT_BOLD
        )
        self.cw = self.font.size("M")[0]
        self.ch = self.font.get_height()
        self.cols = cols
        self.rows = rows
        self.screen = pygame.display.set_mode((cols * self.cw, rows * self.ch))
        self.glyphs = {}

    @property
    def pixel_size(self):
        return self.screen.get_size()

    def clear(self, color=config.BG):
        self.screen.fill(color)

    def put(self, sx, sy, char, color):
        if char == " " or not (0 <= sx < self.cols and 0 <= sy < self.rows):
            return
        key = (char, color)
        glyph = self.glyphs.get(key)
        if glyph is None:
            glyph = self.glyphs[key] = self.font.render(char, True, color)
        self.screen.blit(glyph, (sx * self.cw, sy * self.ch))

    def put_text(self, sx, sy, text, color=config.WHITE):
        for i, char in enumerate(text):
            self.put(sx + i, sy, char, color)

    def put_sprite(self, lines, wx, wy, color, ox):
        bx = int(round(wx)) - ox
        by = int(round(wy))
        for j, line in enumerate(lines):
            for i, char in enumerate(line):
                self.put(bx + i, by + j, char, color)

    def flip(self):
        pygame.display.flip()
