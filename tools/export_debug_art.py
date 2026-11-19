"""Debug art export: PNGs of every converted sprite frame plus a
shape-matched vs plain-ramp comparison sheet.

The sprite pipeline converts pixel-art blocks to (glyph, fg, bg) cells.
This tool renders those conversions to PNGs so the art can be reviewed
outside the game, and puts the shape-matched glyph choice next to a naive
coverage ramp (" .:-=+*#%@") for the same source pixels.

Run from the repo root:

    python tools/export_debug_art.py

Output lands in artifacts/debug/ (gitignored).
"""
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

from emberfall.glyphs import GlyphLibrary, load_font_path
from emberfall.sprite_pipeline import (
    SPRITE_DIR,
    SPRITE_MANIFEST,
    load_sprite_sheet,
)

OUT = ROOT / "artifacts" / "debug"
SCALE = 4
RAMP = " .:-=+*#%@"


def render_frame(frame, glyphs):
    """Render one converted SpriteFrame exactly like the renderer does."""
    surf = pygame.Surface(
        (frame.width * glyphs.cw, frame.height * glyphs.ch),
        pygame.SRCALPHA,
    )
    for row, cells in enumerate(frame.cells):
        for col, cell in enumerate(cells):
            if cell is None:
                continue
            char, fg, bg = cell
            x, y = col * glyphs.cw, row * glyphs.ch
            if bg is not None:
                tile = pygame.Surface((glyphs.cw, glyphs.ch))
                tile.fill(bg)
                surf.blit(tile, (x, y))
            surf.blit(glyphs.surface(char, fg), (x, y))
    return surf


def render_ramp(frame, source, frame_w, frame_h, cell_cols, cell_rows, glyphs):
    """Same colours, but glyphs chosen by coverage only (plain ramp)."""
    block_w = frame_w // cell_cols
    block_h = frame_h // cell_rows
    surf = pygame.Surface(
        (cell_cols * glyphs.cw, cell_rows * glyphs.ch),
        pygame.SRCALPHA,
    )
    for row in range(cell_rows):
        for col in range(cell_cols):
            covered = 0
            for sy in range(row * block_h, (row + 1) * block_h):
                for sx in range(col * block_w, (col + 1) * block_w):
                    if source.get_at((sx, sy)).a > 40:
                        covered += 1
            coverage = covered / (block_w * block_h)
            if coverage < 0.055:
                continue
            cell = frame.cells[row][col]
            fg = cell[1] if cell else (160, 160, 160)
            index = min(len(RAMP) - 1, int(coverage * len(RAMP)))
            char = RAMP[index]
            if char == " ":
                continue
            surf.blit(glyphs.surface(char, fg),
                      (col * glyphs.cw, row * glyphs.ch))
    return surf


def label(text, font, color=(235, 235, 245)):
    return font.render(text, True, color)


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))  # convert_alpha() needs a display surface
    glyphs = GlyphLibrary()
    font = pygame.font.Font(load_font_path(), 14)
    sprite_dir = OUT / "sprites"
    compare_dir = OUT / "compare"
    sprite_dir.mkdir(parents=True, exist_ok=True)
    compare_dir.mkdir(parents=True, exist_ok=True)

    exported = 0
    comparisons = 0
    for name, (filename, fw, fh, cols, rows) in SPRITE_MANIFEST.items():
        frames = load_sprite_sheet(
            SPRITE_DIR / filename, fw, fh, cols, rows, glyphs,
            cache_key="asset:" + filename,
        )
        # Raw source frames for coverage sampling.
        sheet = pygame.image.load(str(SPRITE_DIR / filename)).convert_alpha()
        for index, frame in enumerate(frames):
            converted = render_frame(frame, glyphs)
            big = pygame.Surface(
                (converted.get_width() * SCALE,
                 converted.get_height() * SCALE),
                pygame.SRCALPHA,
            )
            pygame.transform.scale(converted, big.get_size(), big)
            path = sprite_dir / f"{name}_frame{index}.png"
            pygame.image.save(big, str(path))
            exported += 1

            # Source block for this frame.
            source = pygame.Surface((fw, fh), pygame.SRCALPHA)
            source.blit(sheet, (0, 0), (index * fw, 0, fw, fh))
            ramp = render_ramp(frame, source, fw, fh, cols, rows, glyphs)
            ramp_big = pygame.Surface(
                (ramp.get_width() * SCALE, ramp.get_height() * SCALE),
                pygame.SRCALPHA,
            )
            pygame.transform.scale(ramp, ramp_big.get_size(), ramp_big)

            # Side-by-side: shape-matched (left) vs plain ramp (right).
            gap, pad, label_h = 24, 16, 26
            width = big.get_width() + ramp_big.get_width() + gap + pad * 2
            height = max(big.get_height(), ramp_big.get_height()) + \
                label_h + pad * 2
            sheet_out = pygame.Surface((width, height), pygame.SRCALPHA)
            sheet_out.fill((24, 26, 38, 255))
            x = pad
            y = pad + label_h
            for image, caption in (
                (big, f"{name} frame {index}: shape-matched"),
                (ramp_big, f"{name} frame {index}: plain ramp {RAMP!r}"),
            ):
                sheet_out.blit(label(caption, font), (x, pad))
                sheet_out.blit(image, (x, y))
                x += image.get_width() + gap
            cmp_path = compare_dir / f"{name}_frame{index}.png"
            pygame.image.save(sheet_out, str(cmp_path))
            comparisons += 1

    pygame.quit()
    print(f"exported {exported} frame PNGs to {sprite_dir}")
    print(f"exported {comparisons} comparison PNGs to {compare_dir}")


if __name__ == "__main__":
    main()
