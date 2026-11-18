"""Renderer v2 frame-time benchmark and 60 FPS budget check.

Runs a normal route and a deliberately busy mixed-enemy scene, then reports
average / p95 / max milliseconds for every renderer step.  The script exits
non-zero if the average total frame or any individual step exceeds the
60 FPS budget (16.667 ms).

Run from the repo root:  python tests/renderer_v2_benchmark.py
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
from emberfall.entities import Spitter, create_enemy
from emberfall.engine import FixedStepper
from emberfall.input import InputState
from emberfall.renderer import PHASES, Renderer
from emberfall.session import GameSession

BUDGET_MS = 1000.0 / 60.0


def check(name, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {name}"
          + (f"  ({detail})" if detail else ""))
    return bool(condition)


def percentile(values, fraction):
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * fraction))
    return ordered[index]


def run_scene(renderer, label, frames=180, warmup=25, stress=False):
    session = GameSession(seed=11 if stress else 7)
    if stress:
        session.enemies = []
        specs = [
            ("crawler", 8, 10), ("crawler", 14, 10), ("crawler", 22, 10),
            ("crawler", 37, 10), ("crawler", 52, 10), ("crawler", 72, 10),
            ("crawler", 88, 10), ("crawler", 108, 10),
            ("crawler", 128, 10), ("flyer", 10, 8), ("flyer", 18, 10),
            ("flyer", 26, 7), ("flyer", 42, 9), ("flyer", 60, 8),
            ("flyer", 78, 10), ("flyer", 95, 8), ("flyer", 118, 9),
            ("spitter", 15, 10), ("spitter", 25, 10), ("spitter", 34, 10),
            ("spitter", 48, 10), ("spitter", 66, 10), ("spitter", 82, 10),
            ("spitter", 105, 10), ("spitter", 125, 10),
        ]
        session.enemies = [
            create_enemy(kind, x, y, session.rng) for kind, x, y in specs
        ]
        for enemy in session.enemies:
            if isinstance(enemy, Spitter):
                enemy.cooldown = 0.0

    inp = InputState()
    stepper = FixedStepper(session)
    patterns = (
        {"right", "jump", "attack"}, {"right", "jump"},
        {"right", "down", "attack"}, {"right"}, set(),
        {"left", "attack"}, {"left", "jump"}, {"left", "down", "attack"},
        set(), {"right", "attack"},
    )

    # Settle physics once so the measurement does not include level start-up.
    for _ in range(120):
        stepper.advance(config.FIXED_DT, inp)

    totals = []
    updates = []
    phase_values = {name: [] for name in PHASES}
    for i in range(warmup + frames):
        session.player.inv = 999.0
        if stress and i % 20 == 0:
            session.particles.burst(
                session.player.x + 1.5, session.player.y + 1.5,
                16, config.HIT_PARTICLE_COLORS,
            )
            session.projectiles.spawn(
                session.player.x + 8.0, session.player.y + 1.0,
                -10.0, 0.0, color=config.ENEMY_DATA["spitter"]["projectile_color"],
            )
        inp.set_held(set(patterns[i % len(patterns)]))
        t0 = time.perf_counter()
        stepper.advance(config.FIXED_DT, inp)
        update_ms = (time.perf_counter() - t0) * 1000.0
        t1 = time.perf_counter()
        session.draw(renderer)
        renderer.flip()
        frame_ms = (time.perf_counter() - t1) * 1000.0

        if i >= warmup:
            totals.append(frame_ms)
            updates.append(update_ms)
            for name in PHASES:
                phase_values[name].append(renderer.last_times[name])

    print(f"\n{label} ({frames} measured frames)")
    print(f"  simulation/update   avg {sum(updates)/len(updates):6.3f} ms")
    print(f"  full frame          avg {sum(totals)/len(totals):6.3f} ms "
          f"({1000.0 / max(sum(totals)/len(totals), 0.001):5.1f} FPS) | "
          f"p95 {percentile(totals, 0.95):6.3f} | max {max(totals):6.3f}")
    ok = True
    ok &= check(
        f"{label}: average total under 60 FPS budget",
        sum(totals) / len(totals) <= BUDGET_MS,
        f"{sum(totals) / len(totals):.2f} ms <= {BUDGET_MS:.2f} ms",
    )
    for name in PHASES:
        values = phase_values[name]
        avg = sum(values) / len(values)
        ok &= check(
            f"{label}: step '{name}' average under budget",
            avg <= BUDGET_MS,
            f"avg {avg:6.3f} | p95 {percentile(values, 0.95):6.3f} | "
            f"max {max(values):6.3f} ms",
        )
    return ok, {
        "average": sum(totals) / len(totals),
        "p95": percentile(totals, 0.95),
        "max": max(totals),
    }


def main():
    print("Emberfall Renderer v2 frame-time benchmark")
    pygame.init()
    try:
        renderer = Renderer(profile=True)
        normal_ok, normal = run_scene(
            renderer, "Normal demo (7 enemies)", frames=150
        )
        stress_ok, stress = run_scene(
            renderer, "Stress (25 enemies, particles, shots)",
            frames=240, warmup=30, stress=True,
        )
        print("\nSummary:")
        print(f"  normal avg {normal['average']:.2f} ms "
              f"(p95 {normal['p95']:.2f}, max {normal['max']:.2f})")
        print(f"  stress avg {stress['average']:.2f} ms "
              f"(p95 {stress['p95']:.2f}, max {stress['max']:.2f})")
        if normal["p95"] > BUDGET_MS or stress["p95"] > BUDGET_MS:
            print("  INFO  an occasional tail frame exceeded 16.67 ms; "
                  "averages remain within budget.")
        ok = normal_ok and stress_ok
    finally:
        pygame.quit()
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
