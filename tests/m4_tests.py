"""M4 headless tests: multi-key input, Spitter, projectiles, pogo and stress.

Run from the repo root:  python tests/m4_tests.py
No pytest required; exits non-zero on failure.
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import math
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame

from emberfall import combat, config
from emberfall.engine import FixedStepper
from emberfall.entities import Crawler, EnemyState, Spitter, create_enemy
from emberfall.input import InputState, KeyboardInput
from emberfall.projectiles import ProjectileSystem
from emberfall.session import GameSession


DT = config.FIXED_DT


def new_session(clear_enemies=True):
    session = GameSession(seed=7)
    if clear_enemies:
        session.enemies = []
    return session


def advance(session, inp, frames=1):
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


def key_event(event_type, key):
    return pygame.event.Event(event_type, key=key)


def input_tests():
    print("Multi-key input:")
    ok = True

    inp = InputState()
    inp.set_held({"right", "jump", "attack"})
    ok &= check(
        "right+jump+attack latches both edges",
        inp.was_pressed("jump") and inp.was_pressed("attack"),
    )
    ok &= check(
        "right stays held alongside jump and attack",
        inp.axis("left", "right") == 1 and inp.is_held("jump") and inp.is_held("attack"),
    )

    # Both edges must survive a render frame with no physics step, then both
    # must be consumed by one fixed step.
    session = new_session()
    inp = InputState()
    advance(session, inp, 120)
    player = session.player
    stepper = FixedStepper(session)
    start_x = player.x
    inp.set_held({"right", "jump", "attack"})
    steps = stepper.advance(0.001, inp)
    ok &= check(
        "combined edges survive a zero-step frame",
        steps == 0 and inp.was_pressed("jump") and inp.was_pressed("attack"),
    )
    steps = stepper.advance(DT, inp)
    ok &= check(
        "right+jump+attack register in one step",
        steps == 1 and player.vy < 0.0 and player.attacking and player.vx > 0.0,
        f"vy={player.vy:.2f} attack={player.attacking} vx={player.vx:.2f}",
    )
    advance(session, inp, 10)
    ok &= check(
        "running while jumping/attacking keeps moving",
        player.x > start_x + 0.2 and player.vx > 0.0,
        f"dx={player.x - start_x:.2f} vx={player.vx:.2f}",
    )

    # Air attacks retain their horizontal speed while steering or coasting.
    session = new_session()
    inp = InputState()
    advance(session, inp, 120)
    player = session.player
    player.x, player.y = 10.0, 17.0
    player.vx, player.vy = 28.0, 0.0
    player.on_ground = False
    player.inv = 99.0
    inp.set_held({"right", "attack"})
    advance(session, inp, 8)
    ok &= check(
        "air attack keeps horizontal speed",
        player.attacking and abs(player.vx - 28.0) < 1e-6,
        f"vx={player.vx:.3f}",
    )

    session = new_session()
    inp = InputState()
    advance(session, inp, 120)
    player = session.player
    player.x, player.y = 10.0, 17.0
    player.vx, player.vy = 12.0, 0.0
    player.on_ground = False
    player.inv = 99.0
    inp.set_held({"attack"})
    advance(session, inp, 8)
    ok &= check(
        "air attack keeps drifting momentum",
        player.attacking and abs(player.vx - 12.0) < 1e-6,
        f"vx={player.vx:.3f}",
    )

    # Last-pressed-wins at the action level used by scripted input.
    inp = InputState()
    inp.set_held({"left"})
    inp.set_held({"left", "right"})
    right_wins = inp.axis("left", "right")
    inp.set_held({"left"})
    left_restored = inp.axis("left", "right")
    ok &= check(
        "left+right reversal uses last press",
        right_wins == 1 and left_restored == -1,
        f"press-right={right_wins} release-right={left_restored}",
    )

    inp = InputState()
    inp.set_held({"right"})
    inp.set_held({"right", "left"})
    left_wins = inp.axis("left", "right")
    inp.set_held({"right"})
    right_restored = inp.axis("left", "right")
    ok &= check(
        "right+left reversal uses last press",
        left_wins == -1 and right_restored == 1,
        f"press-left={left_wins} release-left={right_restored}",
    )

    # WASD and arrow keys are interchangeable, including duplicate direction
    # keys and releasing the newest key.
    keyboard = KeyboardInput()
    keyboard.handle_events([
        key_event(pygame.KEYDOWN, pygame.K_d),
        key_event(pygame.KEYDOWN, pygame.K_SPACE),
        key_event(pygame.KEYDOWN, pygame.K_j),
    ])
    ok &= check(
        "keyboard latches right+jump+attack together",
        keyboard.axis("left", "right") == 1
        and keyboard.was_pressed("jump")
        and keyboard.was_pressed("attack"),
    )

    keyboard = KeyboardInput()
    keyboard.handle_events([
        key_event(pygame.KEYDOWN, pygame.K_a),
        key_event(pygame.KEYDOWN, pygame.K_RIGHT),
    ])
    arrow_after_wasd = keyboard.axis("left", "right")
    keyboard.handle_events([key_event(pygame.KEYUP, pygame.K_a)])
    arrow_only = keyboard.axis("left", "right")
    keyboard.handle_events([key_event(pygame.KEYUP, pygame.K_RIGHT)])
    released = keyboard.axis("left", "right")
    ok &= check(
        "WASD and arrows mix freely",
        arrow_after_wasd == 1 and arrow_only == 1 and released == 0,
        f"mix={arrow_after_wasd} arrow={arrow_only} release={released}",
    )

    keyboard = KeyboardInput()
    keyboard.handle_events([
        key_event(pygame.KEYDOWN, pygame.K_a),
        key_event(pygame.KEYDOWN, pygame.K_d),
        key_event(pygame.KEYDOWN, pygame.K_LEFT),
    ])
    mixed_left = keyboard.axis("left", "right")
    keyboard.handle_events([key_event(pygame.KEYUP, pygame.K_LEFT)])
    next_held = keyboard.axis("left", "right")
    ok &= check(
        "mixed-key last-press order survives releases",
        mixed_left == -1 and next_held == 1,
        f"left-arrow={mixed_left} release={next_held}",
    )

    keyboard = KeyboardInput()
    keyboard.handle_events([
        key_event(pygame.KEYDOWN, pygame.K_s),
        key_event(pygame.KEYDOWN, pygame.K_DOWN),
    ])
    down_held = keyboard.is_held("down")
    keyboard.handle_events([key_event(pygame.KEYUP, pygame.K_s)])
    down_still_held = keyboard.is_held("down")
    keyboard.handle_events([key_event(pygame.KEYUP, pygame.K_DOWN)])
    ok &= check(
        "S and Down share the held down action",
        down_held and down_still_held and not keyboard.is_held("down"),
    )

    return ok


def spitter_tests():
    print("Spitter and projectiles:")
    ok = True
    data = config.ENEMY_DATA["spitter"]
    ok &= check(
        "spitter windup is 0.5s",
        abs(data["windup_time"] - 0.5) < 1e-9,
        f"{data['windup_time']}s",
    )
    ok &= check(
        "spitter projectile speed is 12-15 cells/s",
        12.0 <= data["projectile_speed"] <= 15.0,
        f"{data['projectile_speed']} cells/s",
    )
    ok &= check(
        "spitter projectile damage is 1",
        data["projectile_damage"] == 1,
    )

    # It retreats when the player gets closer than its preferred band.
    session = new_session()
    inp = InputState()
    advance(session, inp, 120)
    player = session.player
    player.inv = 99.0
    spitter = Spitter(10.0, 22.0, session.rng)
    spitter.cooldown = 99.0  # keep this test in IDLE
    session.enemies = [spitter]
    start_dist = abs((spitter.x + spitter.w / 2.0)
                     - (player.x + player.w / 2.0))
    advance(session, inp, 60)
    end_dist = abs((spitter.x + spitter.w / 2.0)
                   - (player.x + player.w / 2.0))
    ok &= check(
        "spitter keeps its distance",
        end_dist > start_dist + 2.0,
        f"distance {start_dist:.2f} -> {end_dist:.2f}",
    )

    # Full windup order: IDLE -> WINDUP -> ATTACK -> RECOVER -> IDLE.
    session = new_session()
    inp = InputState()
    advance(session, inp, 120)
    player = session.player
    player.inv = 99.0
    spitter = Spitter(18.0, 22.0, session.rng)
    spitter.cooldown = 0.0
    session.enemies = [spitter]
    session.projectiles.clear()

    advance(session, inp, 1)
    ok &= check(
        "spitter starts in IDLE then enters WINDUP",
        spitter.state is EnemyState.WINDUP,
        str(spitter.state),
    )
    ok &= check(
        "spitter windup has colour and telegraph",
        spitter.color == data["windup_color"] and spitter.telegraph,
        str(spitter.color),
    )
    ok &= check(
        "no projectile before the windup finishes",
        len(session.projectiles.items) == 0,
    )

    windup_steps = 0
    while spitter.state is EnemyState.WINDUP and windup_steps < 60:
        advance(session, inp, 1)
        windup_steps += 1
    windup_time = windup_steps * DT
    ok &= check(
        "windup lasts ~0.5s",
        0.48 <= windup_time <= 0.52,
        f"{windup_time:.3f}s",
    )
    ok &= check(
        "WINDUP -> ATTACK and one shot",
        spitter.state is EnemyState.ATTACK
        and len(session.projectiles.items) == 1,
        f"state={spitter.state} shots={len(session.projectiles.items)}",
    )
    ok &= check(
        "attack state changes colour",
        spitter.color == data["attack_color"],
        str(spitter.color),
    )

    if session.projectiles.items:
        shot = session.projectiles.items[0]
        ok &= check(
            "projectile is slow and aimed at the player",
            abs(abs(shot.vx) - data["projectile_speed"]) < 1e-6
            and shot.vx < 0.0
            and shot.damage == 1,
            f"vx={shot.vx:.2f} damage={shot.damage}",
        )
        ok &= check(
            "projectile carries its spitter visuals",
            shot.color == data["projectile_color"]
            and shot.char == data["projectile_char"],
        )

    attack_steps = 0
    while spitter.state is EnemyState.ATTACK and attack_steps < 30:
        advance(session, inp, 1)
        attack_steps += 1
    ok &= check(
        "ATTACK -> RECOVER",
        spitter.state is EnemyState.RECOVER,
        str(spitter.state),
    )
    recover_steps = 0
    while spitter.state is EnemyState.RECOVER and recover_steps < 60:
        advance(session, inp, 1)
        recover_steps += 1
    ok &= check(
        "RECOVER -> IDLE with cooldown",
        spitter.state is EnemyState.IDLE
        and spitter.cooldown == data["cooldown"],
        f"state={spitter.state} cooldown={spitter.cooldown}",
    )

    # Projectiles die on walls, not from their lifetime. A control shot over
    # open ground survives the same number of steps.
    level = session.level
    wall_system = ProjectileSystem()
    wall_system.spawn(59.0, 23.0, 13.0, 0.0)
    for _ in range(30):
        wall_system.update(DT, level)
    ok &= check(
        "projectile is destroyed by a wall",
        len(wall_system.items) == 0,
    )

    control = ProjectileSystem()
    control.spawn(10.0, 23.0, 13.0, 0.0)
    for _ in range(30):
        control.update(DT, level)
    ok &= check(
        "control projectile survives open ground",
        len(control.items) == 1,
    )

    # A projectile deals exactly 1 damage to the player.
    session = new_session()
    inp = InputState()
    advance(session, inp, 120)
    player = session.player
    player.inv = 0.0
    hp_before = player.hp
    session.projectiles.spawn(player.x, player.y, 0.0, 0.0, damage=1)
    advance(session, inp, 1)
    ok &= check(
        "projectile deals 1 damage and is consumed",
        player.hp == hp_before - 1 and len(session.projectiles.items) == 0,
        f"hp={player.hp} shots={len(session.projectiles.items)}",
    )
    ok &= check(
        "projectile hit triggers hurt stop",
        session.hitstop.active,
    )

    # The sword ignores projectiles even when they sit inside its hitbox.
    session = new_session()
    inp = InputState()
    advance(session, inp, 120)
    player = session.player
    player.facing = 1
    player.inv = 99.0
    session.projectiles.spawn(player.x + player.w, player.y, 0.0, 0.0)
    player.start_attack()
    advance(session, inp, 6)
    ok &= check(
        "player cannot slash projectiles",
        len(session.projectiles.items) == 1,
        f"shots={len(session.projectiles.items)}",
    )

    return ok


def pogo_tests():
    print("Pogo:")
    ok = True

    session = new_session()
    inp = InputState()
    advance(session, inp, 120)
    player = session.player
    player.x, player.y = 10.0, 17.0
    player.vx, player.vy = 28.0, 0.0
    player.on_ground = False
    player.inv = 0.0
    crawler = Crawler(10.0, 22.0, session.rng)
    crawler.stun = 99.0
    crawler.vx = 0.0
    session.enemies = [crawler]

    inp.set_held({"right", "down", "attack"})
    hit_frame = None
    for frame in range(8):
        advance(session, inp, 1)
        if crawler.hp < crawler.max_hp:
            hit_frame = frame
            break

    ok &= check(
        "down+attack in air starts a pogo",
        player.pogo and hit_frame is not None,
        f"pogo={player.pogo} frame={hit_frame}",
    )
    ok &= check(
        "pogo hits the enemy below",
        crawler.hp == crawler.max_hp - 2,
        f"hp={crawler.hp}",
    )
    hitbox = combat.attack_hitbox(player)
    ok &= check(
        "pogo hitbox points downward",
        hitbox is not None
        and abs(hitbox[1] - (player.y + player.h)) < 1e-9
        and abs(hitbox[2] - player.w) < 1e-9,
        str(hitbox),
    )
    ok &= check(
        "pogo bounce is ~22 cells/s",
        abs(player.vy + config.POGO_BOUNCE_SPEED) < 1e-6,
        f"vy={player.vy:.2f}",
    )
    ok &= check(
        "pogo triggers hit-stop",
        session.hitstop.active,
    )
    ok &= check(
        "pogo grants no i-frames",
        player.inv <= 0.0,
        f"inv={player.inv:.3f}",
    )
    ok &= check(
        "pogo keeps sideways speed",
        player.vx > 27.0,
        f"vx={player.vx:.2f}",
    )

    return ok


def stress_test():
    print("Mixed-group stress:")
    ok = True
    session = GameSession(seed=11)
    session.enemies = []
    inp = InputState()
    advance(session, inp, 120)
    player = session.player

    specs = [
        ("crawler", 8, 10), ("crawler", 14, 10), ("crawler", 22, 10),
        ("crawler", 37, 10), ("crawler", 52, 10), ("crawler", 72, 10),
        ("crawler", 88, 10), ("crawler", 108, 10), ("crawler", 128, 10),
        ("flyer", 10, 8), ("flyer", 18, 10), ("flyer", 26, 7),
        ("flyer", 42, 9), ("flyer", 60, 8), ("flyer", 78, 10),
        ("flyer", 95, 8), ("flyer", 118, 9),
        ("spitter", 15, 10), ("spitter", 25, 10), ("spitter", 34, 10),
        ("spitter", 48, 10), ("spitter", 66, 10), ("spitter", 82, 10),
        ("spitter", 105, 10), ("spitter", 125, 10),
    ]
    session.enemies = [create_enemy(kind, x, y, session.rng)
                       for kind, x, y in specs]
    for enemy in session.enemies:
        if isinstance(enemy, Spitter):
            enemy.cooldown = 0.0
    kinds = {enemy.kind for enemy in session.enemies}
    start_count = len(session.enemies)
    ok &= check(
        "stress group contains all enemy types",
        {"crawler", "flyer", "spitter"} <= kinds,
        ", ".join(sorted(kinds)),
    )

    patterns = [
        {"right", "jump", "attack"},
        {"right", "jump"},
        {"right", "down", "attack"},
        {"right"},
        set(),
        {"left", "attack"},
        {"left", "jump"},
        {"left", "down", "attack"},
        set(),
        {"right", "attack"},
    ]

    max_projectiles = 0
    saw_projectile = False
    saw_pogo = False
    max_steps = 1200
    error = None
    try:
        for frame in range(max_steps):
            # Keep the stress run alive so it exercises the systems rather
            # than resetting to fresh enemies.
            player.inv = 999.0
            inp.set_held(set(patterns[frame % len(patterns)]))
            session.update(DT, inp)
            inp.clear_edges()

            max_projectiles = max(max_projectiles, len(session.projectiles.items))
            saw_projectile |= bool(session.projectiles.items)
            saw_pogo |= abs(player.vy + config.POGO_BOUNCE_SPEED) < 1e-6

            if not (math.isfinite(player.x) and math.isfinite(player.y)
                    and math.isfinite(player.vx) and math.isfinite(player.vy)):
                raise AssertionError("player state became non-finite")
            for enemy in session.enemies:
                if not (math.isfinite(enemy.x) and math.isfinite(enemy.y)
                        and math.isfinite(enemy.state_time)):
                    raise AssertionError(f"{enemy.kind} state became non-finite")
            for projectile in session.projectiles.items:
                if not (math.isfinite(projectile.x)
                        and math.isfinite(projectile.y)):
                    raise AssertionError("projectile state became non-finite")
    except Exception as exc:  # pragma: no cover - only printed on failure
        traceback.print_exc()
        error = repr(exc)

    ok &= check(
        f"{max_steps} mixed-group steps completed",
        error is None,
        error or f"enemies {start_count}->{len(session.enemies)}",
    )
    ok &= check(
        "stress run stayed alive and finite",
        player.hp == player.max_hp and math.isfinite(player.x),
        f"hp={player.hp} x={player.x:.2f}",
    )
    ok &= check(
        "spitters fired during the stress run",
        saw_projectile,
        f"max_projectiles={max_projectiles}",
    )
    ok &= check(
        "projectile count stayed bounded",
        max_projectiles <= 64,
        f"max={max_projectiles}",
    )
    if saw_pogo:
        print("  INFO  pogo bounce occurred during stress")
    return ok


def main():
    print("Emberfall M4 tests")
    results = [
        input_tests(),
        spitter_tests(),
        pogo_tests(),
        stress_test(),
    ]
    ok = all(results)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
