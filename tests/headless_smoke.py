"""M2 headless smoke + mechanics checks.

Run from the repo root:  python tests/headless_smoke.py
No pytest required; exits non-zero on failure.
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame

from emberfall import combat, config
from emberfall.engine import FixedStepper
from emberfall.entities import Crawler
from emberfall.input import InputState
from emberfall.renderer import Renderer
from emberfall.session import GameSession


DT = config.FIXED_DT


def new_session(clear_enemies=True):
    session = GameSession(seed=7)
    if clear_enemies:
        session.enemies = []
    return session


def advance(session, inp, frames=1):
    """Run fixed steps the way the engine does: edges consumed each step."""
    for _ in range(frames):
        session.update(DT, inp)
        inp.clear_edges()


def settled_session():
    session = new_session()
    inp = InputState()
    advance(session, inp, 120)
    return session, inp


def check(name, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    return bool(condition)


def jump_height(session, inp, release_immediately=False):
    p = session.player
    y0 = p.y
    inp.set_held({"jump"})
    if release_immediately:
        inp.set_held(set())
    advance(session, inp, 1)
    min_y = p.y
    for _ in range(60):
        advance(session, inp, 1)
        min_y = min(min_y, p.y)
    return y0 - min_y


def mechanics():
    print("Mechanics:")
    ok = True

    # Full held jump.
    s, inp = settled_session()
    height = jump_height(s, inp)
    ok &= check("held jump ~5 rows", 4.3 <= height <= 5.3, f"{height:.2f} rows")

    # Tap released before the first physics step must be a short hop.
    s, inp = settled_session()
    tap = jump_height(s, inp, release_immediately=True)
    ok &= check("tap jump is cut", 0.8 <= tap <= 3.0, f"{tap:.2f} rows")

    # A jump buffered in the air must be cut if the key is already released
    # by the time it fires on landing (the starter's KEYUP bug).
    s = new_session()
    inp = InputState()
    p = s.player
    p.x, p.y, p.vy = 10.0, 10.0, 0.0
    p.on_ground = False
    p.coyote = 0.0
    frames_to_land = 0
    while not p.on_ground and frames_to_land < 200:
        advance(s, inp, 1)
        frames_to_land += 1

    s = new_session()
    inp = InputState()
    p = s.player
    p.x, p.y, p.vy = 10.0, 10.0, 0.0
    p.on_ground = False
    p.coyote = 0.0
    advance(s, inp, max(0, frames_to_land - 3))
    inp.set_held({"jump"})
    inp.set_held(set())  # pressed and released before landing
    buffered_vy = None
    for _ in range(15):
        advance(s, inp, 1)
        if p.vy < -5.0:
            buffered_vy = p.vy
            break
    ok &= check("buffered jump released early is cut",
                buffered_vy is not None and -20.0 < buffered_vy < -5.0,
                f"vy={buffered_vy}")

    # Run speed.
    s, inp = settled_session()
    inp.set_held({"right"})
    advance(s, inp, 60)
    ok &= check("run speed settles at 28", abs(abs(s.player.vx) - config.RUN_SPEED) < 0.1,
                f"{s.player.vx:.2f}")

    # Attack windows and one hit per swing.
    s, inp = settled_session()
    inp.set_held({"attack"})
    advance(s, inp, 1)
    inp.set_held(set())
    active = []
    for f in range(30):
        advance(s, inp, 1)
        if combat.attack_hitbox(s.player) is not None:
            active.append(f)
    ok &= check("slash active ~0.12s", len(active) in (7, 8),
                f"{len(active)} frames")

    # Attack is refused during stun.
    s, inp = settled_session()
    s.player.stun = 0.2
    inp.set_held({"attack"})
    advance(s, inp, 1)
    ok &= check("stun blocks attack", not s.player.attacking)

    # Three hits kill, with contact damage disabled for the test.
    s, inp = settled_session()
    p = s.player
    p.inv = 999.0
    enemy = Crawler(p.x + 3.2, p.y, s.rng)
    s.enemies = [enemy]
    hp_sequence = []
    for swing in range(3):
        while p.attacking:
            advance(s, inp, 1)
        enemy.x, enemy.y = p.x + 3.2, p.y
        enemy.vx = enemy.vy = 0.0
        enemy.stun = 99.0
        if enemy not in s.enemies:
            s.enemies.append(enemy)
        hp_before = enemy.hp
        p.start_attack()
        for _ in range(30):
            advance(s, inp, 1)
            if enemy.hp < hp_before:
                break
        hp_sequence.append(enemy.hp)
        advance(s, inp, 20)
    ok &= check("crawler dies in 3 hits", hp_sequence == [2, 1, 0] and not s.enemies,
                str(hp_sequence))

    # Contact damage, knockback, i-frames.
    s, inp = settled_session()
    p = s.player
    s.enemies = [Crawler(p.x + 1.0, p.y, s.rng)]
    hp0 = p.hp
    advance(s, inp, 1)
    ok &= check("contact damage + knockback + i-frames",
                p.hp == hp0 - 1 and p.inv > 0.9 and p.vy < 0 and abs(p.vx) > 1,
                f"hp={p.hp} inv={p.inv:.2f}")
    hp1 = p.hp
    for _ in range(30):
        s.enemies[0].x, s.enemies[0].y = p.x, p.y
        advance(s, inp, 1)
    ok &= check("i-frames block follow-up damage", p.hp == hp1)

    # Coyote time.
    s = new_session()
    inp = InputState()
    p = s.player
    p.x, p.y, p.vy = 93.0, 18.0, 0.0
    p.on_ground = True
    p.coyote = config.COYOTE_TIME
    advance(s, inp, 1)
    inp.set_held({"right"})
    for _ in range(120):
        advance(s, inp, 1)
        if not p.on_ground:
            break
    inp.set_held(set())
    advance(s, inp, 2)
    inp.set_held({"jump"})
    advance(s, inp, 1)
    ok &= check("coyote jump fires just after ledge", p.vy < -5.0, f"vy={p.vy:.2f}")

    # Crawler turns at ledge without falling.
    s = new_session()
    inp = InputState()
    p = s.player
    p.x, p.y = 4.0, 22.0
    enemy = Crawler(93.0, 19.0, s.rng)
    enemy.dir = 1
    s.enemies = [enemy]
    initial_dir = enemy.dir
    for _ in range(40):
        advance(s, inp, 1)
        if enemy.dir != initial_dir:
            break
    ok &= check("crawler turns at ledge",
                enemy.dir == -1 and enemy.y <= 19.1)

    # Crawler turns at wall.
    s = new_session()
    inp = InputState()
    p = s.player
    p.x, p.y = 4.0, 22.0
    enemy = Crawler(56.0, 23.0, s.rng)
    enemy.dir = 1
    s.enemies = [enemy]
    advance(s, inp, 90)
    ok &= check("crawler turns at wall", enemy.vx < 0)

    # Death respawns cleanly.
    s = new_session()
    inp = InputState()
    p = s.player
    p.hp = 1
    p.inv = 0.0
    s.enemies = [Crawler(p.x, p.y, s.rng)]
    advance(s, inp, 1)
    ok &= check("death resets player and enemies",
                s.player.hp == config.PLAYER_MAX_HP and len(s.enemies) == 7,
                f"hp={s.player.hp}, enemies={len(s.enemies)}")

    # Input edges must survive render frames that contain no physics step.
    s = new_session()
    inp = InputState()
    stepper = FixedStepper(s)
    for _ in range(120):
        stepper.advance(1.0 / 60.0, inp)
    stepper.accumulator = 0.0
    inp.set_held({"jump"})
    stepper.advance(0.001, inp)
    retained = s.player.jump_buf <= 0.0 and not s.player.attacking
    stepper.advance(config.FIXED_DT, inp)
    ok &= check("input edge survives zero-step render frame",
                retained and s.player.vy < 0.0,
                f"vy={s.player.vy:.2f}")

    return ok


def scripted_actions(step):
    """A simple route keyed to fixed-step count (blocks of 30)."""
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


def draw_smoke():
    print("Draw / play smoke:")
    pygame.init()
    renderer = Renderer()
    print(f"  cell {renderer.cw}x{renderer.ch} | "
          f"window {renderer.pixel_size[0]}x{renderer.pixel_size[1]}")
    session = GameSession(seed=7)
    inp = InputState()
    stepper = FixedStepper(session)

    for _ in range(900):
        inp.set_held(scripted_actions(stepper.steps))
        stepper.advance(1.0 / 60.0, inp)
        session.draw(renderer)
        renderer.flip()

    p = session.player
    screenshot = Path(tempfile.gettempdir()) / "emberfall_m2_smoke.png"
    pygame.image.save(renderer.screen, str(screenshot))
    ok = (
        stepper.steps == 900
        and 0 <= p.hp <= config.PLAYER_MAX_HP
        and p.x == p.x  # NaN guard
        and p.y == p.y
    )
    ok &= check("900 rendered frames without exception", True,
                f"steps={stepper.steps}, screenshot={screenshot}")
    return ok


def main():
    print("Emberfall M2 headless smoke test")
    ok = mechanics()
    ok &= draw_smoke()
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
