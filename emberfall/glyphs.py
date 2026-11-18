"""Glyph coverage, shape matching and cached coloured glyph surfaces.

The bundled DejaVu Sans Mono font is rasterised once into fixed-size cells.
Each glyph becomes a bit mask; a source image cell is converted by choosing
the glyph whose mask best matches the source coverage (XOR distance plus a
coverage penalty).  Matching and rendered surfaces are cached because the
same sprite cells and foreground colours recur every frame.
"""
from __future__ import annotations

from pathlib import Path

import pygame

from . import config

ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "assets"

# ASCII plus the high-coverage block/box glyphs used by the terrain renderer.
_EXTRA_GLYPHS = "\u2588\u2593\u2592\u2591\u2580\u2584\u258c\u2590\u2550\u2551\u2502\u2500\u250c\u2510\u2514\u2518\u251c\u2524\u252c\u2534\u253c"


def _font_path():
    path = Path(config.GLYPH_FONT_PATH)
    if not path.is_absolute():
        path = ROOT / path
    return str(path)


def _bits_from_surface(surface, cw, ch, threshold=32):
    """Return a row-major bit mask for a rendered glyph cell."""
    bits = 0
    index = 0
    for y in range(ch):
        for x in range(cw):
            if surface.get_at((x, y)).a > threshold:
                bits |= 1 << index
            index += 1
    return bits


class GlyphLibrary:
    """Font metrics, glyph masks, density variants and colour caches."""

    def __init__(self, cw=config.GLYPH_CELL_W, ch=config.GLYPH_CELL_H,
                 font_size=config.GLYPH_FONT_SIZE, bold=config.GLYPH_FONT_BOLD,
                 font_path=None):
        self.cw = cw
        self.ch = ch
        self.font = pygame.font.Font(font_path or _font_path(), font_size)
        self.font.set_bold(bold)
        self.area = cw * ch
        self._surfaces = {}
        self._match_cache = {}
        self._variants = {}
        self._glyphs = {}
        self._build_glyphs()

    # ------------------------------------------------------------------
    # Glyph atlas
    # ------------------------------------------------------------------
    def _render_white(self, char):
        rendered = self.font.render(char, True, (255, 255, 255))
        cell = pygame.Surface((self.cw, self.ch), pygame.SRCALPHA)
        cell.blit(rendered, ((self.cw - rendered.get_width()) // 2,
                             (self.ch - rendered.get_height()) // 2))
        return cell

    def _build_glyphs(self):
        question = self._render_white("?")
        q_bits = _bits_from_surface(question, self.cw, self.ch)
        q_size = question.get_size()

        chars = [chr(i) for i in range(33, 127)] + list(_EXTRA_GLYPHS)
        seen = set()
        for char in chars:
            if char in seen:
                continue
            seen.add(char)
            cell = self._render_white(char)
            bits = _bits_from_surface(cell, self.cw, self.ch)
            coverage = bits.bit_count() / self.area
            if coverage <= 0.0:
                continue
            # Unsupported characters fall back to '?'. Skip those duplicates.
            if char != "?" and bits == q_bits and cell.get_size() == q_size:
                continue
            self._glyphs[char] = (bits, coverage)
        if not self._glyphs:
            raise RuntimeError("font produced no usable glyphs")

        # A small, deterministic set of density targets per glyph. Lighting
        # picks a tier, which changes both stroke density and perceived shape.
        self._density_keys = (0.36, 0.78, 1.18)
        for char, (bits, coverage) in self._glyphs.items():
            tiers = []
            for target_scale in self._density_keys:
                target = max(0.02, min(0.98, coverage * target_scale))
                best = char
                best_score = 1 << 60
                for cand, (cand_bits, cand_cov) in self._glyphs.items():
                    score = ((bits ^ cand_bits).bit_count()
                             + abs(cand_cov - target) * self.area * 2.4)
                    if score < best_score:
                        best_score = score
                        best = cand
                tiers.append(best)
            self._variants[char] = tuple(tiers)

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    @property
    def glyph_count(self):
        return len(self._glyphs)

    def coverage(self, char):
        return self._glyphs.get(char, (0, 0.0))[1]

    def match_mask(self, bits):
        """Choose the glyph whose coverage mask best matches ``bits``."""
        cached = self._match_cache.get(bits)
        if cached is not None:
            return cached
        source_cov = bits.bit_count() / self.area
        best = " "
        best_score = 1 << 60
        for char, (glyph_bits, glyph_cov) in self._glyphs.items():
            score = ((bits ^ glyph_bits).bit_count()
                     + abs(source_cov - glyph_cov) * self.area * 1.6)
            if score < best_score:
                best_score = score
                best = char
        self._match_cache[bits] = best
        return best

    def density_char(self, char, level):
        """Return a sparser/denser variant for a 0..1 light level."""
        if char == " " or char not in self._variants:
            return char
        tiers = self._variants[char]
        if level < 0.40:
            return tiers[0]
        if level < 0.78:
            return tiers[1]
        return tiers[2]

    # ------------------------------------------------------------------
    # Cached colour rendering
    # ------------------------------------------------------------------
    def surface(self, char, color):
        key = (char, color)
        cached = self._surfaces.get(key)
        if cached is not None:
            return cached
        cell = pygame.Surface((self.cw, self.ch), pygame.SRCALPHA)
        if char != " ":
            rendered = self.font.render(char, True, color)
            cell.blit(rendered, ((self.cw - rendered.get_width()) // 2,
                                 (self.ch - rendered.get_height()) // 2))
        self._surfaces[key] = cell
        return cell

    def clear_cache(self):
        self._surfaces.clear()
        self._match_cache.clear()


def quantize_color(color, step=8):
    """Reduce colour churn for glyph-surface caching (still per-cell tint)."""
    return tuple((channel // step) * step for channel in color[:3])


def tint(color, multiplier):
    """Multiply an RGB colour by a 0..1-ish scalar or an RGB multiplier."""
    if isinstance(multiplier, (int, float)):
        return tuple(max(0, min(255, int(channel * multiplier))) for channel in color[:3])
    return tuple(
        max(0, min(255, (channel * m) // 255))
        for channel, m in zip(color[:3], multiplier)
    )


def load_font_path():
    """Expose the resolved path for diagnostics and tests."""
    return _font_path()
