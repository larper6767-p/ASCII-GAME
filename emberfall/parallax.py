"""Pre-rendered parallax layers and fog for Renderer v2.

All expensive shape work happens once. Each frame only a handful of cached
surfaces are blitted with scroll offsets derived from the camera.
"""
from __future__ import annotations

import math
import random

import pygame

from . import config


def _normalized(color):
    """Scale a colour so its brightest channel hits 255 (hue-only tint)."""
    peak = max(1, max(color))
    scale = 255.0 / peak
    return tuple(min(255, int(c * scale)) for c in color)


def _tint_surface(surface, color):
    """Multiply a surface's RGB by a normalised colour, preserving alpha."""
    surface.fill(_normalized(color), special_flags=pygame.BLEND_RGB_MULT)


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Parallax:
    def __init__(self, screen_w, screen_h, world_tile_w,
                 level_width=config.DEMO_LEVEL_WIDTH):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.world_tile_w = world_tile_w
        self.max_scroll_px = max(0, level_width - config.COLS) * world_tile_w
        self.factors = config.PARALLAX_FACTORS
        self.layers = []
        self.fog_overlay = None
        self.fog_strips = []
        self.last_offsets = []
        self.atmosphere = None
        self.atmosphere_key = None
        self.set_atmosphere(None)

    # ------------------------------------------------------------------
    def set_atmosphere(self, atmosphere):
        """Rebuild the cached layers for a room palette and fog density.

        Called when the active room changes; the cost is hidden by the door
        fade. Re-applying the same palette is a no-op.
        """
        if atmosphere is None:
            atmosphere = config.default_atmosphere()
        key = (
            atmosphere.get("sky", config.ATMO_SKY),
            atmosphere.get("rock", config.ATMO_ROCK),
            atmosphere.get("accent", config.ATMO_ACCENT),
            atmosphere.get("fog", config.ATMO_FOG),
            atmosphere.get("ember", config.ATMO_EMBER),
        )
        if key == self.atmosphere_key:
            return
        self.atmosphere_key = key
        self.atmosphere = atmosphere
        self.layers.clear()
        self.fog_strips.clear()
        self.fog_overlay = None
        self.last_offsets.clear()
        self._build()

    # ------------------------------------------------------------------
    def _new_layer(self, factor, depth):
        shift = int(self.max_scroll_px * factor)
        width = self.screen_w + shift + 8
        low_w = max(32, width // 3 + 2)
        low_h = max(24, self.screen_h // 3 + 2)
        low = pygame.Surface((low_w, low_h), pygame.SRCALPHA)
        self._paint_layer(low, low_w, low_h, depth)
        # Tint the pre-rendered depth art towards the room palette. The near
        # layer is tinted with the sky so its silhouettes read as shadowed
        # rock, then its ember specks are repainted in the room ember colour.
        if depth == 0:
            tint_color = self.atmosphere["sky"]
        elif depth == 1:
            tint_color = self.atmosphere["rock"]
        else:
            tint_color = self.atmosphere["sky"]
        _tint_surface(low, tint_color)
        if depth == 2:
            rng = random.Random(90210 + depth * 37 + 1)
            ember = self.atmosphere["ember"]
            for _ in range(28):
                x = rng.randrange(low_w)
                y = rng.randrange(low_h)
                low.set_at((x, y), (ember[0], ember[1], ember[2], 120))
        full = pygame.transform.scale(low, (width, self.screen_h))
        self.layers.append((factor, full, depth))

    def _paint_layer(self, s, w, h, depth):
        rng = random.Random(90210 + depth * 37)
        horizon = int(h * (0.42 + depth * 0.055))
        if depth == 0:
            # Distant mountain silhouettes.
            s.fill((14, 18, 32, 255))
            for band in range(3):
                base = horizon - band * max(2, h // 18)
                points = [(0, h)]
                x = 0
                while x <= w:
                    peak = base - rng.randint(max(2, h // 14), max(4, h // 6))
                    points.append((x, peak))
                    x += rng.randint(max(4, w // 22), max(8, w // 10))
                points.extend([(w, h), (0, h)])
                shade = 24 + band * 10
                pygame.draw.polygon(s, (shade, shade + 5, shade + 20, 255), points)
            for _ in range(max(10, w // 5)):
                x = rng.randrange(w)
                y = rng.randrange(0, max(1, horizon - 3))
                s.set_at((x, y), (130, 160, 210, 210))
        elif depth == 1:
            # Mid-ground ruins and broken columns.
            s.fill((18, 16, 28, 255))
            pygame.draw.rect(s, (24, 22, 36, 255),
                             (0, horizon, w, h - horizon))
            for _ in range(max(5, w // 28)):
                x = rng.randrange(0, max(1, w - 4))
                top = rng.randrange(max(4, horizon // 3), max(6, horizon))
                col_w = rng.randint(2, 5)
                pygame.draw.rect(s, (44, 38, 54, 255),
                                 (x, top, col_w, horizon - top + 2))
                pygame.draw.rect(s, (62, 54, 74, 255),
                                 (x - 1, top, col_w + 2, 1))
                if rng.random() < 0.55:
                    pygame.draw.rect(s, (30, 27, 41, 255),
                                     (x, top, col_w, max(1, (horizon - top) // 3)))
            for _ in range(max(8, w // 12)):
                x = rng.randrange(w)
                y = rng.randrange(max(1, horizon - 3), max(2, h - 1))
                s.set_at((x, y), (120, 92, 90, 150))
        else:
            # Near silhouettes stay in the bottom corners: short, semi-
            # transparent wedges that frame the play area without ever
            # covering it (an earlier version grew to full height and read
            # as a black rectangle bug).
            s.fill((8, 9, 15, 0))
            for side in (0, 1):
                for _ in range(4):
                    base_x = 0 if side == 0 else w
                    width = rng.randint(max(3, w // 16), max(6, w // 10))
                    height = rng.randint(max(6, h // 12), max(8, h // 5))
                    sign = 1 if side == 0 else -1
                    pts = [(base_x, h), (base_x, h - height)]
                    x = base_x
                    for step in range(4):
                        x += sign * max(1, width // 4)
                        y = h - height + rng.randint(-height // 5, height // 4)
                        pts.append((x, y))
                    pts.append((base_x + sign * width, h))
                    pygame.draw.polygon(s, (5, 6, 11, 110), pts)

    def _build(self):
        for depth, factor in enumerate(self.factors):
            self._new_layer(factor, depth)

        density = max(
            0.0, min(1.0, self.atmosphere.get("fog", config.ATMO_FOG))
        )
        if not config.QUALITY_FOG or density <= 0.0:
            # Quality toggle off (or a clear room): no fog bank or strips.
            return

        fog_color = _mix(self.atmosphere["rock"], (150, 158, 184), 0.35)
        # A cached vertical fog bank. Alpha is stronger low in the frame.
        fog = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        for y in range(self.screen_h):
            t = y / max(1, self.screen_h - 1)
            alpha = int((18 + 70 * (t ** 1.7)) * density)
            if alpha <= 0:
                continue
            pygame.draw.line(fog, (*fog_color, alpha),
                             (0, y), (self.screen_w, y))
        self.fog_overlay = fog
        # Bake the static fog bank into the opaque distant layers. This keeps
        # the per-frame cost to a few cached blits instead of a full-screen
        # alpha pass.
        for _factor, surface, depth in self.layers:
            if depth < 2:
                surface.blit(fog, (0, 0))

        # Two slowly drifting fog strips, pre-rendered once.
        for index in range(2):
            strip = pygame.Surface((self.screen_w * 2, self.screen_h // 3),
                                   pygame.SRCALPHA)
            rng = random.Random(4242 + index)
            drawn = False
            for _ in range(18):
                x = rng.randrange(-self.screen_w // 4, self.screen_w * 2)
                y = rng.randrange(0, self.screen_h // 3)
                rx = rng.randrange(self.screen_w // 8, self.screen_w // 2)
                ry = rng.randrange(3, max(4, self.screen_h // 30))
                alpha = int(rng.randrange(18, 40) * density)
                if alpha <= 0:
                    continue
                pygame.draw.ellipse(
                    strip, (*fog_color, alpha),
                    (x - rx // 2, y - ry // 2, rx, ry),
                )
                drawn = True
            if drawn:
                self.fog_strips.append(strip)

    # ------------------------------------------------------------------
    def draw(self, screen, camera_offset_px):
        batch = []
        offsets = []
        for factor, surface, _depth in self.layers:
            ox = int(camera_offset_px * factor)
            offsets.append(ox)
            batch.append((surface, (-ox, 0)))
        self.last_offsets = offsets
        screen.blits(batch, doreturn=False)

        # The fog bank is baked into the distant layers; only the slow
        # drifting strips remain as separate alpha blits (runtime toggle).
        if config.QUALITY_FOG:
            for index, strip in enumerate(self.fog_strips):
                factor = 0.06 + index * 0.035
                ox = int(camera_offset_px * factor) % max(1, strip.get_width() // 2)
                y = int(self.screen_h * (0.38 + index * 0.27))
                screen.blit(strip, (-ox, y))


class LightLayer:
    """Per-cell light levels and an RGB tint surface."""

    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.count = cols * rows
        self.levels = bytearray(self.count)
        self.surface = pygame.Surface((cols, rows)).convert()
        self.ambient = bytearray(self.count)
        ambient = config.LIGHT_AMBIENT
        for y in range(rows):
            # Slightly brighter low in the frame; config owns the baseline.
            t = y / max(1, rows - 1)
            level = int(255 * ambient * (0.78 + 0.42 * t))
            for x in range(cols):
                self.ambient[y * cols + x] = min(255, level)
        self.levels[:] = self.ambient
        self._kernels = {}
        self.light_sources = []
        self._tint_cache = {}
        self._radial_cache = {}
        self.ambient_surface = pygame.Surface((cols, rows)).convert()
        for y in range(rows):
            for x in range(cols):
                self.ambient_surface.set_at(
                    (x, y), self.tint(self.ambient[y * cols + x])
                )

    def reset(self):
        self.levels[:] = self.ambient
        self.light_sources.clear()

    def _kernel(self, radius):
        radius = max(1, int(radius))
        cached = self._kernels.get(radius)
        if cached is not None:
            return cached
        offsets = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                dist = math.hypot(dx, dy) / radius
                if dist <= 1.0:
                    amount = int(255 * (1.0 - dist) ** 1.6)
                    offsets.append((dx, dy, amount))
        result = tuple(offsets)
        self._kernels[radius] = result
        return result

    def add_light(self, cx, cy, radius, strength, color=(255, 236, 190)):
        """Add a radial light source, clamped to the visible light grid."""
        radius = max(1, int(radius))
        amount_scale = max(0.0, min(2.0, strength))
        self.light_sources.append(
            (int(cx), int(cy), radius, color, amount_scale)
        )
        kernel = self._kernel(radius)
        cols, rows = self.cols, self.rows
        for dx, dy, amount in kernel:
            x = int(cx) + dx
            y = int(cy) + dy
            if 0 <= x < cols and 0 <= y < rows:
                index = y * cols + x
                value = self.levels[index] + int(amount * amount_scale)
                self.levels[index] = 255 if value > 255 else value

    def _radial_tint(self, radius, color, strength):
        key = (radius, color, int(strength * 16))
        cached = self._radial_cache.get(key)
        if cached is not None:
            return cached
        size = radius * 2 + 1
        surf = pygame.Surface((size, size)).convert()
        surf.fill((0, 0, 0))
        for dx, dy, amount in self._kernel(radius):
            value = int(amount * strength)
            if value <= 0:
                continue
            surf.set_at(
                (radius + dx, radius + dy),
                (min(255, color[0] * value // 255),
                 min(255, color[1] * value // 255),
                 min(255, color[2] * value // 255)),
            )
        self._radial_cache[key] = surf
        return surf

    def level(self, x, y):
        if 0 <= x < self.cols and 0 <= y < self.rows:
            return self.levels[y * self.cols + x]
        return 0

    def level_px(self, px, py, cw, ch):
        return self.level(px // cw, py // ch)

    def tint(self, level):
        """Return a cached 0..255 RGB tint for a light level."""
        key = level // 8
        cached = self._tint_cache.get(key)
        if cached is not None:
            return cached
        t = min(1.0, key * 8 / 255.0)
        # Cold ambient shadows shifting towards warm light.
        color = (
            int(84 + 171 * t),
            int(94 + 161 * t),
            int(132 + 123 * t),
        )
        self._tint_cache[key] = color
        return color

    def build_surface(self):
        """Compose the per-cell RGB light layer with a few cached blits."""
        surf = self.surface
        surf.blit(self.ambient_surface, (0, 0))
        for cx, cy, radius, color, strength in self.light_sources:
            radial = self._radial_tint(radius, color, strength)
            surf.blit(
                radial, (cx - radius, cy - radius),
                special_flags=pygame.BLEND_RGB_ADD,
            )
        return surf
