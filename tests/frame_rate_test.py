"""M2: render rate must not change simulation results.

Runs the same fixed-step input script with frame deltas for 30, 60 and
144 FPS, then compares the player state after the same number of physics
steps. Run from the repo root:  python tests/frame_rate_test.py
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from emberfall.engine import FixedStepper
from emberfall.input import InputState
from emberfall.session import GameSession


TARGET_STEPS = 360  # 6 seconds of physics


def scripted_actions(step):
    """Same actions for every fixed step, regardless of render cadence."""
    block = (step // 30) % 12
    return (
        set(),
        {"right"},
        {"right", "jump"},
        {"right"},
        {"left"},
        {"left", "jump"},
        {"left"},
        {"attack"},
        {"attack", "right"},
        {"right"},
        {"right", "jump"},
        {"right"},
    )[block]


def run_at(render_fps):
    session = GameSession(seed=7)
    session.enemies = []  # isolate player physics from RNG-driven contact
    inp = InputState()
    stepper = FixedStepper(session)
    frame_dt = 1.0 / render_fps

    while stepper.steps < TARGET_STEPS:
        inp.set_held(scripted_actions(stepper.steps))
        before = stepper.steps
        stepper.advance(frame_dt, inp)
        if stepper.steps == before:
            continue  # high refresh: no physics step this frame

    p = session.player
    return stepper.steps, p.x, p.y, p.vx, p.vy, p.hp


def main():
    print("Emberfall M2 fixed-step / render-rate test")
    results = {}
    for fps in (30, 60, 144):
        steps, x, y, vx, vy, hp = run_at(fps)
        results[fps] = (steps, x, y, vx, vy, hp)
        print(f"  {fps:3d} FPS: steps={steps} pos=({x:.9f}, {y:.9f}) "
              f"vel=({vx:.6f}, {vy:.6f}) hp={hp}")

    ref = results[60]
    worst = 0.0
    for fps, state in results.items():
        dx = abs(state[1] - ref[1])
        dy = abs(state[2] - ref[2])
        worst = max(worst, dx, dy)
        print(f"  delta {fps} FPS vs 60: dx={dx:.9f} dy={dy:.9f}")

    step_counts_equal = all(state[0] == TARGET_STEPS for state in results.values())
    ok = step_counts_equal and worst < 1e-6
    print(f"  max position delta: {worst:.9f} cells")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
