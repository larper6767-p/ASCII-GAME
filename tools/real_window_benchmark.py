"""Real-window frame-time benchmark for both glyph-cell presets.

Unlike tests/renderer_v2_benchmark.py this opens an actual SDL window (no
dummy driver), runs a representative scene, reports per-step ms for the
current frame and saves a screenshot of each preset for visual comparison.

Run from the repo root:

    python tools/real_window_benchmark.py            # both presets
    python tools/real_window_benchmark.py --mode 6x10
    python tools/real_window_benchmark.py --mode 6x10 --room room3 --overlay

`--overlay` enables the in-window F3 overlay (real frame time + per-step
cost) for the measured run, so the screenshot and timings include its cost.
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


def run_mode(mode, frames, save_shot, room, overlay):
    config.set_cell_mode(mode)
    renderer = Renderer(profile=True)
    if overlay:
        renderer.toggle_overlay()
    pygame.display.set_caption(
        f"Emberfall - {room} - cell preset {mode}"
        + (" - F3 overlay" if overlay else "")
    )
    session = GameSession(seed=7) if room == "demo" else GameSession(
        seed=7, room_id=room
    )
    # Start away from the edges so the alternating benchmark pattern does not
    # wander into a door and measure a transition instead of steady play.
    session.player.x = max(8.0, session.level.width * 0.40)
    session.camera.x = max(
        0.0, min(session.level.width - config.COLS, session.player.x - 50)
    )
    inp = InputState()
    stepper = FixedStepper(session)
    patterns = (
        {"right", "jump", "attack"}, {"right", "jump"},
        {"right", "down", "attack"}, {"right"}, set(),
        {"left", "attack"}, {"left", "jump"}, {"left", "down", "attack"},
        set(), {"right", "attack"},
    )

    prev_frame_ms = 1000.0 / 60.0
    for _ in range(90):                      # settle + warm caches
        renderer.note_frame(prev_frame_ms)
        stepper.advance(config.FIXED_DT, inp)
        start = time.perf_counter()
        session.draw(renderer)
        renderer.flip()
        prev_frame_ms = (time.perf_counter() - start) * 1000.0
        pygame.event.pump()

    totals, phase_values = [], {name: [] for name in PHASES}
    shot_saved = False
    for i in range(frames):
        inp.set_held(set(patterns[i % len(patterns)]))
        stepper.advance(config.FIXED_DT, inp)
        renderer.note_frame(prev_frame_ms)
        t0 = time.perf_counter()
        session.draw(renderer)
        renderer.flip()
        prev_frame_ms = (time.perf_counter() - t0) * 1000.0
        totals.append(prev_frame_ms)
        for name in PHASES:
            phase_values[name].append(renderer.last_times[name])
        pygame.event.pump()
        if save_shot and not shot_saved and i == frames // 2:
            path = ROOT / "tools" / f"_room_{room}_{mode}.png"
            pygame.image.save(renderer.screen, str(path))
            print(f"  screenshot: {path}")
            shot_saved = True

    avg = statistics.fmean(totals)
    atmosphere = getattr(session.level, "atmosphere", {})
    print(f"\n=== {room} ({atmosphere.get('name', 'default')})  "
          f"preset {mode}  "
          f"({renderer.pixel_size[0]}x{renderer.pixel_size[1]} window, "
          f"{frames} frames{', F3 overlay' if overlay else ''}) ===")
    print(f"  full frame  avg {avg:6.2f} ms ({1000.0 / avg:5.1f} FPS) | "
          f"p95 {percentile(totals, 0.95):6.2f} | max {max(totals):6.2f}"
          f"{'  <-- BELOW 60 FPS' if avg > BUDGET_MS else ''}")
    worst = []
    if avg > BUDGET_MS:
        worst.append("full frame")
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
    parser.add_argument("--room", default="room1",
                        help="room id under assets/rooms, or 'demo'")
    parser.add_argument("--overlay", action="store_true",
                        help="enable the F3 overlay during measurement")
    args = parser.parse_args()

    modes = ("6x10", "8x14") if args.mode == "both" else (args.mode,)
    pygame.init()
    results = {}
    try:
        for mode in modes:
            results[mode] = run_mode(
                mode, args.frames, save_shot=True,
                room=args.room, overlay=args.overlay,
            )
    finally:
        pygame.quit()

    print("\nSummary:")
    for mode, (avg, worst) in results.items():
        verdict = "OK" if not worst else "BELOW 60 FPS in: " + ", ".join(worst)
        print(f"  {args.room} {mode}: avg {avg:6.2f} ms "
              f"({1000.0 / avg:5.1f} FPS)  {verdict}")


if __name__ == "__main__":
    main()
