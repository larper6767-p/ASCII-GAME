"""Renderer v2 headless tests.

Covers the sub-cell mapping, glyph sprite pipeline, per-cell colours,
shape matching, pixel offsets, lighting/density, parallax/fog, bloom,
blits usage and physics isolation from drawing.

Run from the repo root:  python tests/renderer_v2_tests.py
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame

from emberfall import config
from emberfall.entities import Player
from emberfall.engine import FixedStepper
from emberfall.glyphs import GlyphLibrary, load_font_path
from emberfall.input import InputState
from emberfall.projectiles import ProjectileSystem
from emberfall.renderer import Renderer, PHASES
from emberfall.session import GameSession
from emberfall.sprite_pipeline import (
    SPRITE_DIR,
    SPRITE_MANIFEST,
    load_sprite_sheet,
)


def check(name, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {name}"
          + (f"  ({detail})" if detail else ""))
    return bool(condition)


def mapping_tests(renderer):
    print("Sub-cell world mapping:")
    ok = True
    ok &= check(
        "one physics tile is 2x2 glyph cells",
        renderer.sub == 2,
        f"scale={renderer.sub}",
    )
    ok &= check(
        "glyph cells are 6x10 px",
        (renderer.cw, renderer.ch) == (6, 10),
        f"{renderer.cw}x{renderer.ch}",
    )
    ok &= check(
        "world tile pixel size follows the glyph grid",
        renderer.world_tile_w == renderer.cw * renderer.sub
        and renderer.world_tile_h == renderer.ch * renderer.sub,
        f"{renderer.world_tile_w}x{renderer.world_tile_h}",
    )
    expected = (
        config.COLS * renderer.sub * renderer.cw,
        config.ROWS * renderer.sub * renderer.ch,
    )
    ok &= check(
        "window is physics view x sub-cells",
        renderer.pixel_size == expected,
        f"{renderer.pixel_size[0]}x{renderer.pixel_size[1]}",
    )
    # Physics values must still be float cell units, untouched by rendering.
    baseline = {
        "PLAYER_W": 3, "PLAYER_H": 3, "RUN_SPEED": 28.0,
        "GRAVITY": 95.0, "FIXED_DT": 1.0 / 60.0,
        "COLS": 100, "ROWS": 28,
    }
    for name, value in baseline.items():
        ok &= check(
            f"physics constant unchanged: {name}={value}",
            getattr(config, name) == value,
        )
    frac_x = renderer.world_px(4.33, 20.0, 0)[0]
    whole_x = renderer.world_px(4.0, 20.0, 0)[0]
    ok &= check(
        "entities use sub-cell pixel offsets",
        frac_x != whole_x and frac_x > whole_x,
        f"x 4.0 -> {whole_x}, 4.33 -> {frac_x}",
    )
    ok &= check(
        "camera offset subtracts from world pixels",
        renderer.world_px(10.0, 20.0, 2)
        == (8 * renderer.world_tile_w, 20 * renderer.world_tile_h),
    )
    return ok


def glyph_tests(renderer):
    print("Glyph coverage and shape matching:")
    ok = True
    glyphs = renderer.glyphs
    ok &= check(
        "bundled monospace font was loaded",
        Path(load_font_path()).is_file(),
        load_font_path(),
    )
    ok &= check(
        "font produced a usable glyph atlas",
        glyphs.glyph_count >= 90,
        f"{glyphs.glyph_count} glyphs",
    )

    area = glyphs.cw * glyphs.ch
    full_bits = (1 << area) - 1
    full_char = glyphs.match_mask(full_bits)
    ok &= check(
        "a fully covered source cell matches a dense block glyph",
        glyphs.coverage(full_char) >= 0.70,
        f"{ascii(full_char)} coverage={glyphs.coverage(full_char):.2f}",
    )

    diag_bits = 0
    for y in range(glyphs.ch):
        x = min(glyphs.cw - 1, y * glyphs.cw // glyphs.ch)
        diag_bits |= 1 << (y * glyphs.cw + x)
    diag_char = glyphs.match_mask(diag_bits)
    ok &= check(
        "a sparse diagonal matches a sparse glyph",
        0.0 < glyphs.coverage(diag_char) < 0.55,
        f"{ascii(diag_char)} coverage={glyphs.coverage(diag_char):.2f}",
    )
    ok &= check(
        "shape matching is cached and deterministic",
        glyphs.match_mask(diag_bits) == diag_char,
    )

    dark = glyphs.density_char("\u2593", 0.12)
    bright = glyphs.density_char("\u2593", 0.96)
    ok &= check(
        "lighting shifts glyph density",
        glyphs.coverage(dark) < glyphs.coverage(bright),
        f"dark={ascii(dark)}/{glyphs.coverage(dark):.2f} "
        f"bright={ascii(bright)}/{glyphs.coverage(bright):.2f}",
    )
    return ok


def sprite_pipeline_tests(renderer):
    print("Pixel-art PNG -> glyph frame pipeline:")
    ok = True
    missing = [
        filename for filename, *_ in SPRITE_MANIFEST.values()
        if not (SPRITE_DIR / filename).is_file()
    ]
    ok &= check(
        "all bundled sprite PNGs exist",
        not missing,
        ", ".join(missing) if missing else f"{len(SPRITE_MANIFEST)} files",
    )

    sizes = {
        "player": (6, 6), "crawler": (6, 4), "flyer": (10, 4),
        "spitter": (6, 6), "shot": (2, 2),
    }
    for name, expected_size in sizes.items():
        frames = renderer.sprites.frame(name, 0, 1)
        ok &= check(
            f"{name} frame is {expected_size[0]}x{expected_size[1]} cells",
            (frames.width, frames.height) == expected_size,
            f"{frames.width}x{frames.height}",
        )

    player_frame = renderer.sprites.frame("player", 0, 1)
    filled = [cell for row in player_frame.cells for cell in row if cell]
    with_bg = [cell for cell in filled if cell[2] is not None]
    valid = all(len(cell) == 3 and isinstance(cell[0], str)
                and len(cell[1]) == 3 for cell in filled)
    ok &= check(
        "converted sprite cells carry fg/bg colour data",
        len(filled) > 10 and len(with_bg) > 0 and valid,
        f"{len(filled)} cells, {len(with_bg)} with backgrounds",
    )

    sprite_path = SPRITE_DIR / SPRITE_MANIFEST["player"][0]
    sprite_args = SPRITE_MANIFEST["player"][1:]
    cache_key = "asset:" + SPRITE_MANIFEST["player"][0]
    stats_before = renderer.sprites.cache_stats()["hits"]
    first = load_sprite_sheet(
        sprite_path, *sprite_args, renderer.glyphs, cache_key=cache_key,
    )
    stats_after = renderer.sprites.cache_stats()["hits"]
    second = load_sprite_sheet(
        sprite_path, *sprite_args, renderer.glyphs, cache_key=cache_key,
    )
    ok &= check(
        "sprite conversion results are cached",
        first is second and stats_after > stats_before,
        f"hits {stats_before}->{stats_after}",
    )

    left = renderer.sprites.frame("player", 0, -1)
    ok &= check(
        "left-facing frames mirror without changing size",
        left.width == player_frame.width
        and left.height == player_frame.height
        and left.cells != player_frame.cells,
    )
    return ok


def lighting_tests(renderer):
    print("Per-cell lighting layer:")
    ok = True
    layer = renderer.light_layer
    layer.reset()
    far_level = layer.level(5, 5)
    ambient_level = int(layer.ambient[5 * layer.cols + 5])
    ok &= check(
        "ambient layer has one level per render cell",
        layer.count == renderer.sub_cols * renderer.sub_rows
        and abs(far_level - ambient_level) <= 2,
        f"far={far_level} ambient={ambient_level}",
    )
    layer.add_light(renderer.sub_cols // 2, renderer.sub_rows // 2,
                    8, 1.0)
    near_level = layer.level(renderer.sub_cols // 2, renderer.sub_rows // 2)
    ok &= check(
        "light sources raise the per-cell level",
        near_level > far_level + 40,
        f"near={near_level} far={far_level}",
    )
    ok &= check(
        "light tints get brighter with level",
        sum(layer.tint(240)) > sum(layer.tint(40)),
    )

    player = Player(10.0, 20.0)
    system = ProjectileSystem()
    renderer.update_lighting(player, [], system, 0)
    px = int((player.x + player.w / 2.0) * renderer.sub)
    py = int((player.y + player.h / 2.0) * renderer.sub)
    lit_player = layer.level(px, py)
    lit_far = layer.level(1, 1)
    ok &= check(
        "scene lights are integrated into the layer",
        lit_player > lit_far + 20,
        f"player={lit_player} far={lit_far}",
    )
    ok &= check(
        "the tint surface is per render cell",
        layer.surface.get_size() == (renderer.sub_cols, renderer.sub_rows),
    )
    return ok


def parallax_bloom_tests(renderer):
    print("Parallax, fog and bloom:")
    ok = True
    parallax = renderer.parallax
    ok &= check(
        "three parallax layers are pre-rendered",
        len(parallax.layers) == len(config.PARALLAX_FACTORS),
        f"{len(parallax.layers)} layers",
    )
    ok &= check(
        "layers are wider than the screen for scrolling",
        all(surface.get_width() > renderer.pixel_size[0]
            for _factor, surface, _depth in parallax.layers),
    )
    ok &= check(
        "a static fog bank and drifting fog strips exist",
        parallax.fog_overlay is not None and len(parallax.fog_strips) == 2,
    )

    target = pygame.Surface(renderer.pixel_size).convert()
    parallax.draw(target, 0)
    offsets_near = list(parallax.last_offsets)
    parallax.draw(target, 800)
    offsets_far = list(parallax.last_offsets)
    ok &= check(
        "parallax scroll is depth-scaled",
        offsets_near != offsets_far
        and offsets_far[0] < offsets_far[1] < offsets_far[2],
        f"{offsets_near} -> {offsets_far}",
    )

    renderer.bloom.begin()
    before_blobs = len(renderer.bloom._blobs)
    target.fill((0, 0, 0))
    renderer.bloom.add(renderer.pixel_size[0] // 2,
                       renderer.pixel_size[1] // 2, 40, (255, 220, 120), 1.0)
    renderer.bloom.finish(target)
    ok &= check(
        "bloom accumulates cached glow blobs and adds light",
        renderer.bloom.stats["glows"] >= 1
        and len(renderer.bloom._blobs) > before_blobs
        and target.get_at((target.get_width() // 2,
                           target.get_height() // 2))[0] > 0,
    )
    return ok


def draw_scene_tests(renderer):
    print("Scene drawing and blits:")
    ok = True
    session = GameSession(seed=7)
    inp = InputState()
    stepper = FixedStepper(session)
    for i in range(12):
        inp.set_held({"right", "attack"} if i % 2 else {"right"})
        stepper.advance(config.FIXED_DT, inp)
        session.draw(renderer)
        renderer.flip()

    ok &= check(
        "draw+flip advances profiler frames",
        renderer.frame_index >= 12,
    )
    ok &= check(
        "all renderer steps report timings",
        set(PHASES) <= set(renderer.last_times),
        ", ".join(sorted(renderer.last_times)),
    )
    ok &= check(
        "terrain and sprites contribute glyph batches",
        renderer.stats["terrain_cells"] > 500
        and renderer.stats["sprite_cells"] > 50,
        f"terrain={renderer.stats['terrain_cells']} "
        f"sprites={renderer.stats['sprite_cells']}",
    )
    ok &= check(
        "Surface.blits is used for foreground/background batches",
        renderer.stats["glyph_blits"] > 500
        and renderer.stats["background_blits"] >= 1,
        f"glyph_blits={renderer.stats['glyph_blits']}",
    )
    sky = renderer.screen.get_at((renderer.pixel_size[0] // 2, 5))
    ground = renderer.screen.get_at(
        (renderer.pixel_size[0] // 2,
         (config.ROWS - 1) * renderer.sub * renderer.ch + 1)
    )
    ok &= check(
        "rendered screen contains distinct sky/ground detail",
        sky != ground,
        f"sky={sky} ground={ground}",
    )
    return ok


def physics_isolation_test(renderer):
    print("Physics isolation from drawing:")
    ok = True

    def run(draw_frames):
        session = GameSession(seed=7)
        inp = InputState()
        stepper = FixedStepper(session)
        patterns = (
            {"right"}, {"right", "jump"}, {"right", "attack"},
            {"left"}, {"left", "jump"}, {"down", "attack"}, set(),
        )
        for i in range(48):
            inp.set_held(patterns[i % len(patterns)])
            stepper.advance(config.FIXED_DT, inp)
            if draw_frames:
                session.draw(renderer)
                renderer.flip()
        return (
            session.time, session.player.x, session.player.y,
            session.player.vx, session.player.vy, session.player.hp,
            [(e.kind, e.x, e.y, e.state_time) for e in session.enemies],
        )

    plain = run(False)
    drawn = run(True)
    ok &= check(
        "drawing does not change fixed-step simulation state",
        plain == drawn,
        f"time {plain[0]:.6f} vs {drawn[0]:.6f}, "
        f"player x {plain[1]:.6f} vs {drawn[1]:.6f}",
    )
    return ok


def budget_test(renderer):
    print("Renderer budget smoke (30 rendered frames):")
    ok = True
    session = GameSession(seed=7)
    inp = InputState()
    stepper = FixedStepper(session)
    totals = []
    phase_totals = {name: [] for name in PHASES}
    for i in range(40):
        inp.set_held({"right", "attack"} if i % 3 == 0 else {"right"})
        stepper.advance(config.FIXED_DT, inp)
        start = time.perf_counter()
        session.draw(renderer)
        renderer.flip()
        totals.append((time.perf_counter() - start) * 1000.0)
        for name in PHASES:
            phase_totals[name].append(renderer.last_times[name])
    warm = totals[10:]
    average = sum(warm) / len(warm)
    ok &= check(
        "average frame stays under the 60 FPS budget",
        average <= 1000.0 / 60.0,
        f"{average:.2f} ms ({1000.0 / max(average, 0.001):.1f} FPS)",
    )
    for name in PHASES:
        avg = sum(phase_totals[name][10:]) / len(warm)
        ok &= check(
            f"step '{name}' average stays under budget",
            avg <= 1000.0 / 60.0,
            f"{avg:.2f} ms",
        )
    return ok


def main():
    print("Emberfall Renderer v2 tests")
    pygame.init()
    try:
        renderer = Renderer(profile=True)
        results = [
            mapping_tests(renderer),
            glyph_tests(renderer),
            sprite_pipeline_tests(renderer),
            lighting_tests(renderer),
            parallax_bloom_tests(renderer),
            draw_scene_tests(renderer),
            physics_isolation_test(renderer),
            budget_test(renderer),
        ]
        ok = all(results)
    finally:
        pygame.quit()
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
