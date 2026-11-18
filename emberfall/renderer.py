"""Renderer v2: sub-cell glyph grid, pixel-offset sprites and lighting.

One physics cell is rendered as GLYPH_SCALE x GLYPH_SCALE small glyph cells.
The physics simulation never sees this grid.  Background cells are built in a
tiny per-cell surface, tinted by a per-cell light layer and scaled up in one
operation.  Foreground cells are cached coloured glyphs gathered into a
single Surface.blits batch.  Entities and particles use pixel offsets, so
motion is smooth even though the world itself is tile-based.

Per-step timings are available in ``Renderer.last_times`` when profiling is
enabled (``Renderer(profile=True)`` or config.RENDER_PROFILE).
"""
from __future__ import annotations

import time

import pygame

from . import config, fx
from . import sprites as ascii_sprites
from .bloom import Bloom
from .glyphs import GlyphLibrary, quantize_color, tint
from .parallax import LightLayer, Parallax
from .sprite_pipeline import SpriteLibrary

PHASES = (
    "clear", "parallax", "lighting", "terrain", "sprites",
    "particles", "hud", "flush", "bloom", "present",
)


class _NullPhase:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


_NULL_PHASE = _NullPhase()


class _Timer:
    __slots__ = ("renderer", "name", "t0")

    def __init__(self, renderer, name):
        self.renderer = renderer
        self.name = name

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.renderer.frame_times[self.name] += (
            time.perf_counter() - self.t0
        ) * 1000.0
        return False


class Renderer:
    """Character-grid renderer with a per-(glyph, colour) surface cache."""

    def __init__(self, cols=config.COLS, rows=config.ROWS,
                 profile=config.RENDER_PROFILE):
        self.cols = cols
        self.rows = rows
        self.sub = config.GLYPH_SCALE
        self.cw = config.GLYPH_CELL_W
        self.ch = config.GLYPH_CELL_H
        self.sub_cols = cols * self.sub
        self.sub_rows = rows * self.sub
        self.world_tile_w = self.cw * self.sub
        self.world_tile_h = self.ch * self.sub
        self.profile = profile

        self.screen = pygame.display.set_mode(
            (self.sub_cols * self.cw, self.sub_rows * self.ch)
        )
        self._screen_size = self.screen.get_size()
        self.glyphs = GlyphLibrary()
        self.sprites = SpriteLibrary(self.glyphs)
        self.font = self.glyphs.font
        self._bg_scaled = pygame.Surface(self._screen_size,
                                         pygame.SRCALPHA).convert_alpha()
        self._lit_bg = pygame.Surface((self.sub_cols, self.sub_rows),
                                      pygame.SRCALPHA)
        self._solid_cache = {}
        self._style_cache = {}
        self._fg_batch = []
        self._bg_batch = []
        self._terrain_fg_cache = {}
        self._tile_bg_cache = {}
        self._world_bg_surface = None
        self._world_static_by_x = None
        self._world_grass_by_x = None
        self._world_level = None
        self._active_level = None

        self.parallax = Parallax(
            self._screen_size[0], self._screen_size[1], self.world_tile_w
        )
        self.light_layer = LightLayer(self.sub_cols, self.sub_rows)
        self.bloom = Bloom(self._screen_size[0], self._screen_size[1])

        self.frame_times = {name: 0.0 for name in PHASES}
        self.last_times = dict(self.frame_times)
        self.frame_index = 0
        self.stats = {
            "glyph_blits": 0,
            "background_blits": 0,
            "foreground_blits": 0,
            "sprite_cells": 0,
            "particle_cells": 0,
            "terrain_cells": 0,
        }
        self._ox = 0

    # ------------------------------------------------------------------
    # Timing helpers
    # ------------------------------------------------------------------
    def _phase(self, name):
        if self.profile:
            return _Timer(self, name)
        return _NULL_PHASE

    @property
    def pixel_size(self):
        return self._screen_size

    # ------------------------------------------------------------------
    # Frame setup / present
    # ------------------------------------------------------------------
    def begin_frame(self, camera_offset=0):
        with self._phase("clear"):
            self._ox = camera_offset
            self.frame_times = {name: 0.0 for name in PHASES}
            self._fg_batch.clear()
            self._bg_batch.clear()
            self.stats.update(
                glyph_blits=0, background_blits=0, foreground_blits=0,
                sprite_cells=0, particle_cells=0, terrain_cells=0,
            )
            self.bloom.begin()
            self.screen.fill(config.BG)

    def flip(self):
        with self._phase("present"):
            pygame.display.flip()
        self.last_times = dict(self.frame_times)
        self.frame_index += 1

    # ------------------------------------------------------------------
    # Background / terrain
    # ------------------------------------------------------------------
    def _background_color(self, tile, wx, sy, above, sx, sy_sub):
        if tile == "#":
            exposed = above not in "#="
            if exposed and sy_sub == 0:
                v = 78 + ((wx * 11 + sy * 7) % 3) * 6
                return (v, v + 3, v + 16, 255)
            if sy_sub == 0:
                v = 62 + ((wx * 7 + sy * 3) % 3) * 5
                return (v, v + 2, v + 14, 255)
            v = 44 + ((wx * 5 + sy * 13 + sx) % 3) * 5
            return (v, v + 2, v + 12, 255)
        if tile == "=":
            if sy_sub == 0:
                return (108, 73, 43, 255)
            return (66, 44, 29, 255)
        if tile == '"':
            return (24, 54, 29, 150)
        # Empty cells stay almost transparent so the parallax and fog layer
        # remain visible; a dark veil ties the room together.
        return (10, 12, 22, 48)

    def _tile_bg_surface(self, tile, wx, sy, above, exposed):
        if tile == "#":
            variant = ((wx * 11 + sy * 7) % 3,
                       (wx * 7 + sy * 3) % 3,
                       (wx * 5 + sy * 13) % 3)
        else:
            variant = ()
        key = (tile, exposed, variant)
        cached = self._tile_bg_cache.get(key)
        if cached is not None:
            return cached
        surf = pygame.Surface((self.sub, self.sub), pygame.SRCALPHA)
        for sub_y in range(self.sub):
            for sub_x in range(self.sub):
                surf.set_at(
                    (sub_x, sub_y),
                    self._background_color(
                        tile, wx, sy, above, sub_x, sub_y
                    ),
                )
        self._tile_bg_cache[key] = surf
        return surf

    def _ensure_world_terrain(self, level):
        """Build one camera-independent background/cell table per level."""
        if self._world_level is level and self._world_bg_surface is not None:
            return
        world_w = max(1, level.width * self.sub)
        world_h = self.sub_rows
        surface = pygame.Surface((world_w, world_h), pygame.SRCALPHA)
        bg_batch = []
        static_by_x = [[] for _ in range(level.width)]
        grass_by_x = [[] for _ in range(level.width)]
        for wx in range(level.width):
            for sy in range(self.rows):
                tile = level.tile_at(wx, sy)
                above = level.tile_at(wx, sy - 1)
                tile_surf = self._tile_bg_surface(
                    tile, wx, sy, above, above not in "#="
                )
                bg_batch.append(
                    (tile_surf, (wx * self.sub, sy * self.sub),
                     None, pygame.BLEND_RGBA_MAX)
                )
                if tile in "#=":
                    for sub_y in range(self.sub):
                        for sub_x in range(self.sub):
                            cell = self._terrain_cell(
                                tile, wx, sy, sub_x, sub_y, above,
                            )
                            if cell is not None:
                                char, color = cell
                                static_by_x[wx].append(
                                    (sy, sub_x, sub_y, char, color)
                                )
                elif tile == '"':
                    for sub_y in range(self.sub):
                        for sub_x in range(self.sub):
                            if sub_y == 0 and (wx + sy + sub_x) % 4 != 0:
                                continue
                            grass_by_x[wx].append(
                                (sy, sub_x, sub_y, wx, sy)
                            )
        surface.blits(bg_batch, doreturn=False)
        self._world_bg_surface = surface
        self._world_static_by_x = tuple(static_by_x)
        self._world_grass_by_x = tuple(grass_by_x)
        self._world_level = level

    def _build_terrain_cache(self, ox, level):
        cached = self._terrain_fg_cache.get(ox)
        if cached is not None:
            return cached
        self._ensure_world_terrain(level)
        surface = pygame.Surface((self.sub_cols, self.sub_rows),
                                 pygame.SRCALPHA)
        # Camera offsets are normally non-negative; the negative case is
        # handled by Pygame clipping when screen shake pulls left of zero.
        surface.blit(self._world_bg_surface, (-ox * self.sub, 0))
        static_cells = []
        grass_cells = []
        for sx in range(self.cols):
            wx = ox + sx
            if not (0 <= wx < len(self._world_static_by_x)):
                continue
            col_base = sx * self.sub
            for sy, sub_x, sub_y, char, color in (
                    self._world_static_by_x[wx]):
                col = col_base + sub_x
                row = sy * self.sub + sub_y
                static_cells.append(
                    (col, row, col * self.cw, row * self.ch,
                     char, color)
                )
            for sy, sub_x, sub_y, gwx, gsy in self._world_grass_by_x[wx]:
                col = col_base + sub_x
                row = sy * self.sub + sub_y
                grass_cells.append(
                    (col, row, col * self.cw, row * self.ch,
                     gwx, gsy, sub_x, sub_y)
                )
        result = (surface, tuple(static_cells), tuple(grass_cells))
        self._terrain_fg_cache[ox] = result
        return result

    def _make_styled_glyph(self, char, color, light):
        density_char = self.glyphs.density_char(char, light / 255.0)
        if density_char == " ":
            return None
        lit_color = quantize_color(
            tint(color, self.light_layer.tint(light))
        )
        return self.glyphs.surface(density_char, lit_color)

    def draw_terrain(self, level, camera_offset, world_time, player):
        with self._phase("terrain"):
            self._active_level = level
            ox = int(round(camera_offset))
            base, static_cells, grass_cells = self._build_terrain_cache(
                ox, level
            )
            lit = self._lit_bg
            lit.fill((0, 0, 0, 0))
            lit.blit(base, (0, 0))
            lit.blit(self.light_layer.surface, (0, 0),
                     special_flags=pygame.BLEND_RGB_MULT)
            pygame.transform.scale(lit, self._screen_size, self._bg_scaled)
            self.screen.blit(self._bg_scaled, (0, 0))
            self.stats["background_blits"] += 1

            levels = self.light_layer.levels
            sub_cols = self.sub_cols
            style_cache = self._style_cache
            batch = self._fg_batch
            append = batch.append
            for col, row, px, py, char, color in static_cells:
                light = levels[row * sub_cols + col]
                if light <= 18:
                    continue
                key = (char, color, light >> 4)
                glyph = style_cache.get(key)
                if glyph is None:
                    glyph = self._make_styled_glyph(char, color, light)
                    style_cache[key] = glyph
                if glyph is not None:
                    append((glyph, (px, py)))
                    self.stats["terrain_cells"] += 1
            for col, row, px, py, wx, sy, sub_x, sub_y in grass_cells:
                char, color = fx.grass_char(wx, sy, player, world_time)
                if sub_x == 1:
                    char = {"|": "/", "/": "|", "\\": "|",
                            "'": ",", "`": "'"}.get(char, char)
                light = levels[row * sub_cols + col]
                if light <= 18:
                    continue
                key = (char, color, light >> 4)
                glyph = style_cache.get(key)
                if glyph is None:
                    glyph = self._make_styled_glyph(char, color, light)
                    style_cache[key] = glyph
                if glyph is not None:
                    append((glyph, (px, py)))
                    self.stats["terrain_cells"] += 1

    def _terrain_cell(self, tile, wx, sy, sub_x, sub_y, above):
        if tile == "#":
            exposed = above not in "#="
            h = (wx * 17 + sy * 31 + sub_x * 7 + sub_y * 13) & 7
            if sub_y == 0 and exposed:
                char = "\u2580"  # upper half block = lit rock lip
                color = (176, 176, 202)
            elif h < 2:
                char = "\u2591"
                color = (105, 105, 132)
            elif h < 5:
                char = "\u2592"
                color = (132, 132, 160)
            else:
                char = "\u2593"
                color = (114, 114, 142)
            return char, color
        if tile == "=":
            if sub_y == 0:
                return "\u2550", (238, 174, 101)
            return "\u2591", (174, 116, 68)
        return None

    # ------------------------------------------------------------------
    # Lighting
    # ------------------------------------------------------------------
    def update_lighting(self, player, enemies, projectiles, camera_offset):
        with self._phase("lighting"):
            self.light_layer.reset()
            if player is not None:
                self.light_layer.add_light(
                    (player.x + player.w / 2.0 - camera_offset) * self.sub,
                    (player.y + player.h / 2.0) * self.sub,
                    config.LIGHT_PLAYER_RADIUS * self.sub,
                    config.LIGHT_PLAYER_STRENGTH,
                    (255, 229, 177),
                )
            for projectile in projectiles.items:
                self.light_layer.add_light(
                    (projectile.x - camera_offset) * self.sub,
                    (projectile.y + 0.5) * self.sub,
                    config.LIGHT_PROJECTILE_RADIUS * self.sub,
                    config.LIGHT_PROJECTILE_STRENGTH,
                    projectile.color,
                )
            for enemy in enemies:
                if getattr(enemy, "telegraph", False):
                    self.light_layer.add_light(
                        (enemy.x + enemy.w / 2.0 - camera_offset) * self.sub,
                        (enemy.y + enemy.h / 2.0) * self.sub,
                        4.5 * self.sub,
                        0.55,
                        enemy.data.get("windup_color", (255, 225, 90)),
                    )
            self.light_layer.build_surface()

    # ------------------------------------------------------------------
    # Parallax
    # ------------------------------------------------------------------
    def draw_parallax(self, camera_offset, world_time=0.0):
        with self._phase("parallax"):
            self.parallax.draw(
                self.screen,
                int(round(camera_offset * self.world_tile_w)),
            )

    # ------------------------------------------------------------------
    # Sprites and particles
    # ------------------------------------------------------------------
    def _world_px(self, wx, wy, ox):
        return (
            int(round((wx - ox) * self.world_tile_w)),
            int(round(wy * self.world_tile_h)),
        )

    def world_px(self, wx, wy, ox=0):
        """Public pixel mapping helper used by tests and effects."""
        return self._world_px(wx, wy, ox)

    def _light_tint_at(self, px, py):
        light = self.light_layer.level_px(px, py, self.cw, self.ch)
        return light, self.light_layer.tint(light)

    def _add_solid(self, color, rect):
        if color is None:
            return
        surf = self._solid_cache.get(color)
        if surf is None:
            surf = pygame.Surface((self.cw, self.ch)).convert()
            surf.fill(color)
            self._solid_cache[color] = surf
        self._bg_batch.append((surf, (rect[0], rect[1])))

    def _draw_frame(self, frame, wx, wy, ox, color_override=None,
                    flash=False):
        if frame is None:
            return
        px, py = self._world_px(wx, wy, ox)
        if px > self._screen_size[0] or px + frame.width * self.cw < 0:
            return
        if py > self._screen_size[1] or py + frame.height * self.ch < 0:
            return

        # A sprite is small enough that one centre light sample gives smooth
        # global lighting without per-cell cost. The terrain and background
        # remain fully per-cell.
        centre_x = px + frame.width * self.cw // 2
        centre_y = py + frame.height * self.ch // 2
        light = self.light_layer.level_px(
            centre_x, centre_y, self.cw, self.ch
        )
        tint_rgb = self.light_layer.tint(light)
        style_cache = self._style_cache
        batch = self._fg_batch
        for row, cells in enumerate(frame.cells):
            for col, cell in enumerate(cells):
                if cell is None:
                    continue
                char, fg, bg = cell
                cx = px + col * self.cw
                cy = py + row * self.ch
                if bg is not None:
                    self._add_solid(
                        quantize_color(tint(bg, tint_rgb)),
                        (cx, cy, self.cw, self.ch),
                    )
                cell_light = light
                if flash:
                    fg = (255, 245, 225)
                    cell_light = 255
                elif color_override is not None:
                    # Preserve per-cell art luminance while shifting the hue
                    # to the enemy's telegraph colour.
                    lum = min(
                        1.0,
                        (fg[0] * 0.3 + fg[1] * 0.55 + fg[2] * 0.15) / 255.0,
                    )
                    fg = tuple(
                        min(255, int(c * (0.35 + lum * 0.9)))
                        for c in color_override
                    )
                key = (char, fg, cell_light >> 4)
                glyph = style_cache.get(key)
                if glyph is None:
                    glyph = self._make_styled_glyph(char, fg, cell_light)
                    style_cache[key] = glyph
                if glyph is not None:
                    batch.append((glyph, (cx, cy)))
                    self.stats["sprite_cells"] += 1

    def draw_enemies(self, enemies, camera_offset):
        with self._phase("sprites"):
            for enemy in enemies:
                data = enemy.data
                state_color = None
                if enemy.color != data["color"]:
                    state_color = enemy.color
                if enemy.kind == "crawler":
                    frame_index = int(enemy.anim * data["anim_fps"]) % 2
                    facing = getattr(enemy, "dir", 1)
                elif enemy.kind == "flyer":
                    frame_index = int(enemy.anim * data["anim_fps"]) % 2
                    facing = enemy.facing
                else:
                    frame_index = int(enemy.anim * data["anim_fps"]) % 2
                    facing = enemy.facing
                frame = self.sprites.frame(enemy.kind, frame_index, facing)
                self._draw_frame(
                    frame, enemy.x, enemy.y, camera_offset,
                    color_override=state_color,
                    flash=enemy.flash > 0.0,
                )
                if enemy.telegraph:
                    px, py = self._world_px(
                        enemy.x + enemy.w / 2.0, enemy.y - 1.0, camera_offset
                    )
                    glyph = self.glyphs.surface(
                        "!", enemy.data["windup_color"]
                    )
                    self._fg_batch.append(
                        (glyph, (px - self.cw // 2, py))
                    )
                    self.bloom.add(
                        px + self.cw // 2, py + self.ch // 2,
                        self.cw * 2.4, enemy.data["windup_color"], 0.9,
                    )

    def draw_player(self, player, camera_offset, time):
        with self._phase("sprites"):
            if player.inv > 0.0 and int(player.inv * 20) % 2 != 0:
                return
            if player.attacking:
                frame_index = 4
            elif not player.on_ground:
                frame_index = 3
            elif abs(player.vx) > 2.0:
                frame_index = 1 + int(player.anim * 10) % 2
            else:
                frame_index = 0
            frame = self.sprites.frame("player", frame_index, player.facing)
            self._draw_frame(frame, player.x, player.y, camera_offset)
            px, py = self._world_px(
                player.x + player.w / 2.0, player.y + player.h / 2.0,
                camera_offset,
            )
            self.bloom.add(px, py, self.cw * 2.8, (100, 180, 255), 0.66)

    def draw_projectiles(self, projectiles, camera_offset):
        with self._phase("sprites"):
            for projectile in projectiles.items:
                frame = self.sprites.frame("shot", 0, 1)
                self._draw_frame(
                    frame, projectile.x, projectile.y, camera_offset,
                    color_override=projectile.color,
                )
                px, py = self._world_px(
                    projectile.x + 0.5, projectile.y + 0.5, camera_offset
                )
                self.put_world_glyph(
                    projectile.char, px, py,
                    (255, 255, 235), glow=True,
                )
                self.bloom.add(px, py, self.cw * 2.2, projectile.color, 1.0)

    def draw_slash(self, player, camera_offset):
        with self._phase("sprites"):
            if not (player.attacking
                    and player.attack_t >= config.ATTACK_STARTUP):
                return
            active = player.attack_t < config.ATTACK_ACTIVE_END
            color = (255, 255, 200) if active else (150, 150, 125)
            if player.pogo:
                lines = ascii_sprites.SLASH_DOWN
                bx, by = player.x, player.y + player.h
            else:
                lines = (ascii_sprites.SLASH if player.facing > 0
                         else ascii_sprites.mirror(ascii_sprites.SLASH))
                by = player.y
                bx = player.x + player.w if player.facing > 0 else (
                    player.x - config.ATTACK_REACH
                )
            px, py = self._world_px(bx, by, camera_offset)
            for row, line in enumerate(lines):
                for col, char in enumerate(line):
                    if char == " ":
                        continue
                    glyph = self.glyphs.surface(char, color)
                    self._fg_batch.append(
                        (glyph, (px + col * self.cw, py + row * self.ch))
                    )
                    if active:
                        self.bloom.add(
                            px + col * self.cw + self.cw // 2,
                            py + row * self.ch + self.ch // 2,
                            self.cw * 1.8, color, 0.8,
                        )

    def draw_particles(self, particles, camera_offset):
        with self._phase("particles"):
            for particle in particles.items:
                px, py = self._world_px(particle.x, particle.y, camera_offset)
                if px < -self.cw or py < -self.ch:
                    continue
                if px > self._screen_size[0] or py > self._screen_size[1]:
                    continue
                light, tint_rgb = self._light_tint_at(px, py)
                color = quantize_color(tint(particle.color, tint_rgb))
                glyph = self.glyphs.surface(particle.char, color)
                self._fg_batch.append((glyph, (px, py)))
                self.stats["particle_cells"] += 1
                if light > 96 or particle.color[0] > 210:
                    self.bloom.add(
                        px + self.cw // 2, py + self.ch // 2,
                        self.cw * 1.5, particle.color, 0.65,
                    )

    # ------------------------------------------------------------------
    # Direct glyph API (HUD / compatibility)
    # ------------------------------------------------------------------
    def put(self, sx, sy, char, color):
        if char == " " or not (0 <= sx < self.sub_cols
                               and 0 <= sy < self.sub_rows):
            return
        self._fg_batch.append(
            (self.glyphs.surface(char, color), (sx * self.cw, sy * self.ch))
        )

    def put_text(self, sx, sy, text, color=config.WHITE):
        for i, char in enumerate(text):
            self.put(sx + i, sy, char, color)

    def put_sprite(self, lines, wx, wy, color, ox):
        px, py = self._world_px(wx, wy, ox)
        for j, line in enumerate(lines):
            for i, char in enumerate(line):
                if char != " ":
                    self.put_world_glyph(char, px + i * self.cw,
                                         py + j * self.ch, color)

    def put_world_glyph(self, char, px, py, color, glow=False):
        if char == " ":
            return
        self._fg_batch.append((self.glyphs.surface(char, color), (px, py)))
        if glow:
            self.bloom.add(
                px + self.cw // 2, py + self.ch // 2,
                self.cw * 1.6, color, 0.65,
            )

    # ------------------------------------------------------------------
    # Finish / flush / bloom
    # ------------------------------------------------------------------
    def flush(self):
        with self._phase("flush"):
            if self._bg_batch:
                self.screen.blits(self._bg_batch, doreturn=False)
                self.stats["background_blits"] += len(self._bg_batch)
                self._bg_batch.clear()
            if self._fg_batch:
                self.screen.blits(self._fg_batch, doreturn=False)
                self.stats["glyph_blits"] += len(self._fg_batch)
                self.stats["foreground_blits"] = len(self._fg_batch)
                self._fg_batch.clear()

    def end_frame(self):
        self.flush()
        with self._phase("bloom"):
            self.bloom.finish(self.screen)

    def draw_hud(self, player, enemies):
        with self._phase("hud"):
            self.put_text(
                2, 1,
                "HP [" + "#" * player.hp + "-" * (player.max_hp - player.hp) + "]",
                config.HUD_HEALTH_COLOR,
            )
            self.put_text(
                2, 2,
                "A/D move  S+J pogo  SPACE jump  J attack  R restart",
                config.HUD_HELP_COLOR,
            )
            if not enemies:
                self.put_text(
                    max(0, self.sub_cols // 2 - 9), 6,
                    "ALL ENEMIES SLAIN",
                    config.HUD_CLEAR_COLOR,
                )

    def clear(self, color=config.BG):
        self.screen.fill(color)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------
    def timing_report(self):
        """Return measured milliseconds per phase for the last frame."""
        return dict(self.last_times)

    def budget_report(self, budget_ms=1000.0 / 60.0):
        """Return phases that exceeded the 60 FPS budget."""
        return {
            name: ms for name, ms in self.last_times.items()
            if ms > budget_ms
        }
