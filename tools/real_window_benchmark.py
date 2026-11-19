"""Real-window frame-time benchmark for both glyph-cell presets.

Unlike tests/renderer_v2_benchmark.py this opens an actual SDL window (no
dummy driver), runs a representative scene, reports per-step ms for the
current frame and saves a screenshot of each preset for visual comparison.

Run from the repo root:

    python tools/real_window_benchmark.py            # both presets
    python tools/real_window_benchmark.py --mode 6x10

Any step whose AVERAGE exceeds 16.67 ms (60 FPS) is flagged in the output.
"""
import argparse
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Deliberately NOT setting SDL_VIDEODRIVER: this must be a real window.
os.environ.pop("SDL_VIDEODRIVER", None)

import pygame

from emberfall import config
from emberfall.engine import FixedStepper
from emberfall.input import InputState
from emberfall.renderer import PHASES, Renderer
from emberfall.session import GameSession

BUDGET_MS = 1000.0 / 60.0


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def run_mode(mode, frames, save_shot):
    config.set_cell_mode(mode)
    renderer = Renderer(profile=True)
    pygame.display.set_caption(f"Emberfall - cell preset {mode}")
    session = GameSession(seed=7)
    inp = InputState()
    stepper = FixedStepper(session)
    patterns = (
        {"right", "jump", "attack"}, {"right", "jump"},
        {"right", "down", "attack"}, {"right"}, set(),
        {"left", "attack"}, {"left", "jump"}, {"left", "down", "attack"},
        set(), {"right", "attack"},
    )

    for _ in range(90):                      # settle + warm caches
        stepper.advance(config.FIXED_DT, inp)
        session.draw(renderer)
        renderer.flip()
        pygame.event.pump()

    totals, phase_values = [], {name: [] for name in PHASES}
    shot_saved = False
    for i in range(frames):
        inp.set_held(set(patterns[i % len(patterns)]))
        stepper.advance(config.FIXED_DT, inp)
        t0 = time.perf_counter()
        session.draw(renderer)
        renderer.flip()
        totals.append((time.perf_counter() - t0) * 1000.0)
        for name in PHASES:
            phase_values[name].append(renderer.last_times[name])
        pygame.event.pump()
        if save_shot and not shot_saved and i == frames // 2:
            path = ROOT / "tools" / f"_cell_{mode}.png"
            pygame.image.save(renderer.screen, str(path))
            print(f"  screenshot: {path}")
            shot_saved = True

    avg = statistics.fmean(totals)
    print(f"\n=== preset {mode}  "
          f"({renderer.pixel_size[0]}x{renderer.pixel_size[1]} window, "
          f"{frames} frames) ===")
    print(f"  full frame  avg {avg:6.2f} ms ({1000.0 / avg:5.1f} FPS) | "
          f"p95 {percentile(totals, 0.95):6.2f} | max {max(totals):6.2f}")
    worst = []
    for name in PHASES:
        values = phase_values[name]
        a = statistics.fmean(values)
        p95 = percentile(values, 0.95)
        flag = "  <-- BELOW 60 FPS" if a > BUDGET_MS else ""
        print(f"  {name:<10} avg {a:6.3f} | p95 {p95:6.3f} | "
              f"max {max(values):6.3f} ms{flag}")
        if a > BUDGET_MS:
            worst.append(name)
    return avg, worst


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("6x10", "8x14", "both"),
                        default="both")
    parser.add_argument("--frames", type=int, default=150)
    args = parser.parse_args()

    modes = ("6x10", "8x14") if args.mode == "both" else (args.mode,)
    pygame.init()
    results = {}
    try:
        for mode in modes:
            results[mode] = run_mode(mode, args.frames, save_shot=True)
    finally:
        pygame.quit()

    print("\nSummary:")
    for mode, (avg, worst) in results.items():
        verdict = "OK" if not worst else "BELOW 60 FPS in: " + ", ".join(worst)
        print(f"  {mode}: avg {avg:6.2f} ms ({1000.0 / avg:5.1f} FPS)  {verdict}")


if __name__ == "__main__":
    main()
