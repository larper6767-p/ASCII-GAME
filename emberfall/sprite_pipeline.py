"""Load tiny pixel-art PNG sheets and convert them to cached glyph frames.

Each output cell stores ``(glyph, foreground, background)``. Fully covered
cells get a dark background; partially transparent edge cells let the world
show through and only draw a foreground glyph.
"""
from __future__ import annotations

from pathlib import Path

import pygame

from . import glyphs as glyph_mod

ROOT = Path(__file__).resolve().parents[1]
SPRITE_DIR = ROOT / "assets" / "sprites"

# name: (file, frame width, frame height, output cell columns, output rows)
SPRITE_MANIFEST = {
    "player": ("player.png", 24, 36, 6, 6),
    "crawler": ("crawler.png", 24, 24, 6, 4),
    "flyer": ("flyer.png", 40, 24, 10, 4),
    "spitter": ("spitter.png", 24, 36, 6, 6),
    "shot": ("shot.png", 8, 12, 2, 2),
}

_MIRROR_TABLE = str.maketrans(
    "/\\()<>[]{}`'.,:;-_/\\|"
    "\u258c\u2590\u250c\u2510\u2514\u2518\u251c\u2524\u252c\u2534"
    "\u2554\u2557\u255a\u255d\u2560\u2563\u2566\u2569",
    "\\/)(><][}{`'.,:;-_\\/|"
    "\u2590\u258c\u2510\u250c\u2518\u2514\u2524\u251c\u2534\u252c"
    "\u2557\u2554\u255d\u255a\u2563\u2560\u2569\u2566",
)

_FRAME_CACHE = {}
_SHEET_CACHE = {}
_CACHE_STATS = {"sheet_loads": 0, "frame_builds": 0, "hits": 0}


class SpriteFrame:
    """A converted sprite frame at glyph-cell resolution."""

    __slots__ = ("cells", "width", "height")

    def __init__(self, cells):
        self.cells = tuple(tuple(row) for row in cells)
        self.height = len(self.cells)
        self.width = len(self.cells[0]) if self.cells else 0

    def mirrored(self):
        rows = []
        for row in self.cells:
            mirrored = []
            for cell in reversed(row):
                if cell is None:
                    mirrored.append(None)
                else:
                    char, fg, bg = cell
                    mirrored.append((char.translate(_MIRROR_TABLE), fg, bg))
            rows.append(tuple(mirrored))
        return SpriteFrame(rows)

    def __repr__(self):
        return f"SpriteFrame({self.width}x{self.height})"


def _load_sheet(path):
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = ROOT / resolved
    key = (str(resolved), resolved.stat().st_mtime_ns)
    cached = _SHEET_CACHE.get(key)
    if cached is not None:
        return cached
    surface = pygame.image.load(str(resolved)).convert_alpha()
    _SHEET_CACHE[key] = surface
    _CACHE_STATS["sheet_loads"] += 1
    return surface


def _cell_from_block(frame, x0, y0, block_w, block_h, cw, ch, glyphs):
    """Sample one source block and convert it to a glyph cell."""
    mask_bits = 0
    index = 0
    alpha_accum = 0
    r_accum = g_accum = b_accum = 0
    weighted = 0
    covered = 0
    total = block_w * block_h
    for gy in range(ch):
        sy = y0 + min(block_h - 1, int(gy * block_h / ch))
        for gx in range(cw):
            sx = x0 + min(block_w - 1, int(gx * block_w / cw))
            color = frame.get_at((sx, sy))
            if color.a > 40:
                mask_bits |= 1 << index
                covered += 1
            alpha_accum += color.a
            if color.a > 0:
                r_accum += color.r * color.a
                g_accum += color.g * color.a
                b_accum += color.b * color.a
                weighted += color.a
            index += 1

    # Alpha sampled over the block gives a more stable density than the
    # nearest-neighbour mask alone.
    block_alpha = 0
    block_covered = 0
    for sy in range(y0, y0 + block_h):
        for sx in range(x0, x0 + block_w):
            c = frame.get_at((sx, sy))
            block_alpha += c.a
            if c.a > 40:
                block_covered += 1
    coverage = block_covered / total
    if coverage < 0.055:
        return None

    if weighted:
        fg = (r_accum // weighted, g_accum // weighted, b_accum // weighted)
    else:
        fg = (160, 160, 160)
    fg = tuple(min(255, channel + 8) for channel in fg)

    # A fully covered cell is better represented by a solid block plus a
    # background colour than by an approximate thin glyph.
    if coverage > 0.94:
        char = "\u2588"
        bg = glyph_mod.tint(fg, 0.42)
    else:
        char = glyphs.match_mask(mask_bits)
        bg = None
    return (char, fg, bg)


def _build_frame(surface, frame_index, frame_w, frame_h, cell_cols, cell_rows,
                 cw, ch, glyphs):
    frame = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
    frame.blit(surface, (0, 0), (frame_index * frame_w, 0, frame_w, frame_h))
    block_w = frame_w // cell_cols
    block_h = frame_h // cell_rows
    rows = []
    for row in range(cell_rows):
        cells = []
        for col in range(cell_cols):
            cells.append(_cell_from_block(
                frame, col * block_w, row * block_h,
                block_w, block_h, cw, ch, glyphs,
            ))
        rows.append(cells)
    return SpriteFrame(rows)


def load_sprite_sheet(path, frame_w, frame_h, cell_cols, cell_rows, glyphs,
                      cache_key=None):
    """Load and convert every frame in a sheet, using a process-wide cache."""
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = ROOT / resolved
    mtime = resolved.stat().st_mtime_ns
    key = (cache_key or str(resolved), mtime, frame_w, frame_h,
           cell_cols, cell_rows, glyphs.cw, glyphs.ch)
    cached = _FRAME_CACHE.get(key)
    if cached is not None:
        _CACHE_STATS["hits"] += 1
        return cached

    sheet = _load_sheet(resolved)
    count = max(1, sheet.get_width() // frame_w)
    frames = []
    for index in range(count):
        frames.append(_build_frame(
            sheet, index, frame_w, frame_h, cell_cols, cell_rows,
            glyphs.cw, glyphs.ch, glyphs,
        ))
        _CACHE_STATS["frame_builds"] += 1
    frames = tuple(frames)
    _FRAME_CACHE[key] = frames
    return frames


class SpriteLibrary:
    """Look up converted frames by entity name, frame index and facing."""

    def __init__(self, glyphs):
        self.glyphs = glyphs
        self._frames = {}
        self._mirrored = {}
        for name, (filename, fw, fh, cols, rows) in SPRITE_MANIFEST.items():
            self._frames[name] = load_sprite_sheet(
                SPRITE_DIR / filename, fw, fh, cols, rows, glyphs,
                cache_key="asset:" + filename,
            )

    @property
    def loaded_names(self):
        return tuple(sorted(self._frames))

    def frame(self, name, index=0, facing=1):
        frames = self._frames.get(name)
        if not frames:
            return None
        frame = frames[index % len(frames)]
        if facing >= 0:
            return frame
        key = (name, index % len(frames))
        mirrored = self._mirrored.get(key)
        if mirrored is None:
            mirrored = self._mirrored[key] = frame.mirrored()
        return mirrored

    def cache_stats(self):
        return dict(_CACHE_STATS)


def reset_caches():
    """Test helper: drop all conversion caches and stats."""
    _FRAME_CACHE.clear()
    _SHEET_CACHE.clear()
    for key in _CACHE_STATS:
        _CACHE_STATS[key] = 0
