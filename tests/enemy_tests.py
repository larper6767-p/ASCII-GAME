"""M3 headless tests for the enemy framework, Crawler and Flyer.

Run from the repo root:  python tests/enemy_tests.py
No pytest required; exits non-zero on failure.
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from emberfall import combat, config
from emberfall.entities import Crawler, EnemyState, Flyer
from emberfall.input import InputState
from emberfall.physics import collides
from emberfall.session import GameSession


DT = config.FIXED_DT


def new_session(clear_enemies=True):
    session = GameSession(seed=7)
    if clear_enemies:
        session.enemies = []
    return session


def settled_session():
    session = new_session()
    inp = InputState()
    advance(session, inp, 120)
    return session, inp


def advance(session, inp, frames=1):
    for _ in range(frames):
        session.update(DT, inp)
        inp.clear_edges()


def check(name, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {name}"
          + (f"  ({detail})" if detail else ""))
    return bool(condition)


def data_tests():
    print("Enemy data / base framework:")
    ok = True
    required = {
        "w", "h", "hp", "speed", "windup_time", "attack_time",
        "recover_time", "contact_damage", "contact_states",
        "knockback_x", "knockback_y", "stun_time", "flash_time",
    }
    for kind in ("crawler", "flyer"):
        missing = required - set(config.ENEMY_DATA[kind])
        ok &= check(f"{kind} stats live in ENEMY_DATA", not missing,
                    f"missing={sorted(missing)}" if missing else "")

    session = new_session()
    crawler = Crawler(10.0, 10.0, session.rng)
    flyer = Flyer(10.0, 10.0, session.rng)
    cdata = config.ENEMY_DATA["crawler"]
    fdata = config.ENEMY_DATA["flyer"]
    ok &= check(
        "crawler starts in PATROL with data hp/size",
        crawler.state is EnemyState.PATROL
        and crawler.hp == cdata["hp"]
        and (crawler.w, crawler.h) == (cdata["w"], cdata["h"]),
    )
    ok &= check(
        "flyer starts in FLOAT with data hp/size",
        flyer.state is EnemyState.FLOAT
        and flyer.hp == fdata["hp"]
        and (flyer.w, flyer.h) == (fdata["w"], fdata["h"]),
    )
    ok &= check("flyer windup is ~0.45s",
                abs(fdata["windup_time"] - 0.45) < 1e-9,
                f"{fdata['windup_time']:.2f}s")

    hit_target = Crawler(20.0, 10.0, session.rng)
    hp_before = hit_target.hp
    killed = hit_target.take_hit(1)
    ok &= check(
        "base hit applies data knockback/stun/flash",
        not killed
        and hit_target.hp == hp_before - 1
        and hit_target.vx == cdata["knockback_x"]
        and hit_target.vy == cdata["knockback_y"]
        and hit_target.stun == cdata["stun_time"]
        and hit_target.flash == cdata["flash_time"],
    )
    return ok


def crawler_tests():
    print("Crawler:")
    ok = True

    s, inp = settled_session()
    p = s.player
    p.inv = 0.0
    crawler = Crawler(p.x + 1.0, p.y, s.rng)
    s.enemies = [crawler]
    hp0 = p.hp
    advance(s, inp, 1)
    ok &= check("contact damage in PATROL",
                p.hp == hp0 - 1 and crawler.contact_damage_enabled,
                f"hp={p.hp}")

    # The smoke test already covers wall/ledge turns and three-hit death;
    # check that the M3 state-machine fields are still present and active.
    ok &= check("state timer advances",
                crawler.state_time > 0.0, f"{crawler.state_time:.3f}s")
    return ok


def flyer_float_test():
    print("Flyer float:")
    s, inp = settled_session()
    p = s.player
    p.x, p.y = 4.0, 22.0
    flyer = Flyer(60.0, 10.0, s.rng)
    s.enemies = [flyer]
    home_center_y = flyer.home_y
    centers = []
    for _ in range(120):
        advance(s, inp, 1)
        centers.append(flyer.y + flyer.h / 2.0)

    travel = max(centers) - min(centers)
    ok = (
        flyer.state is EnemyState.FLOAT
        and max(centers) < 14.0
        and min(centers) > 7.0
        and 0.5 < travel < 3.0
    )
    return check("hovers without gravity on a sine path", ok,
                 f"state={flyer.state.value} travel={travel:.2f} "
                 f"home={home_center_y:.1f}")


def flyer_state_sequence_test():
    print("Flyer state machine:")
    ok = True
    s, inp = settled_session()
    p = s.player
    flyer = Flyer(p.x + 7.0, 14.0, s.rng)
    s.enemies = [flyer]

    steps = 0
    while flyer.state is not EnemyState.WINDUP and steps < 10:
        advance(s, inp, 1)
        steps += 1
    ok &= check("FLOAT -> WINDUP", flyer.state is EnemyState.WINDUP,
                f"steps={steps}")

    data = config.ENEMY_DATA["flyer"]
    ok &= check("windup colour and telegraph are visible",
                flyer.telegraph
                and flyer.color == data["windup_color"]
                and flyer.color != data["color"],
                f"color={flyer.color}")

    windup_frames = 0
    while flyer.state is EnemyState.WINDUP and windup_frames < 120:
        advance(s, inp, 1)
        windup_frames += 1
    windup_time = windup_frames * DT
    ok &= check("WINDUP -> DIVE after ~0.45s",
                flyer.state is EnemyState.DIVE
                and 0.43 <= windup_time <= 0.47,
                f"{windup_time:.3f}s")
    ok &= check("DIVE is the dangerous state",
                flyer.contact_damage_enabled)
    ok &= check("dive points toward the player", flyer.dive_dy > 0.5,
                f"dir=({flyer.dive_dx:.2f}, {flyer.dive_dy:.2f})")

    dive_frames = 0
    while flyer.state is EnemyState.DIVE and dive_frames < 120:
        advance(s, inp, 1)
        dive_frames += 1
    ok &= check("DIVE -> RECOVER", flyer.state is EnemyState.RECOVER,
                f"after {dive_frames * DT:.2f}s")

    recover_start_distance = (
        (flyer.x + flyer.w / 2.0 - flyer.home_x) ** 2
        + (flyer.y + flyer.h / 2.0 - flyer.home_y) ** 2
    ) ** 0.5
    recover_frames = 0
    while flyer.state is EnemyState.RECOVER and recover_frames < 120:
        advance(s, inp, 1)
        recover_frames += 1
    recover_end_distance = (
        (flyer.x + flyer.w / 2.0 - flyer.home_x) ** 2
        + (flyer.y + flyer.h / 2.0 - flyer.home_y) ** 2
    ) ** 0.5
    ok &= check("RECOVER -> FLOAT", flyer.state is EnemyState.FLOAT,
                f"after {recover_frames * DT:.2f}s")
    ok &= check("recover retreats toward home",
                recover_end_distance < recover_start_distance,
                f"{recover_start_distance:.2f} -> {recover_end_distance:.2f}")
    return ok


def flyer_contact_test():
    print("Flyer contact states:")
    ok = True
    dangerous = {
        EnemyState.FLOAT: False,
        EnemyState.WINDUP: False,
        EnemyState.DIVE: True,
        EnemyState.RECOVER: False,
    }
    s = new_session()
    for state, expected in dangerous.items():
        flyer = Flyer(10.0, 10.0, s.rng)
        flyer.set_state(state)
        ok &= check(f"contact {state.value} == {expected}",
                    flyer.contact_damage_enabled is expected)

    data = config.ENEMY_DATA["flyer"]
    for state, expected in dangerous.items():
        s, inp = settled_session()
        p = s.player
        p.inv = 0.0
        flyer = Flyer(p.x, p.y, s.rng)
        flyer.set_state(state)
        if state is EnemyState.DIVE:
            # Keep the overlap for this one-step damage check.
            flyer.dive_dx = flyer.dive_dy = 0.0
        s.enemies = [flyer]
        hp0 = p.hp
        advance(s, inp, 1)
        took_damage = p.hp == hp0 - data["contact_damage"]
        ok &= check(f"overlap in {state.value} damages == {expected}",
                    took_damage is expected,
                    f"hp={p.hp}")
    return ok


def flyer_hit_test():
    print("Flyer hittability / death:")
    ok = True
    states = (
        EnemyState.FLOAT,
        EnemyState.WINDUP,
        EnemyState.DIVE,
        EnemyState.RECOVER,
    )
    for state in states:
        s, inp = settled_session()
        p = s.player
        p.inv = 999.0
        flyer = Flyer(p.x + 3.2, p.y, s.rng)
        flyer.stun = 99.0
        flyer.set_state(state)
        s.enemies = [flyer]
        hp0 = flyer.hp
        p.start_attack()
        hit = False
        for _ in range(20):
            advance(s, inp, 1)
            if flyer.hp < hp0:
                hit = True
                break
        ok &= check(f"hit lands in {state.value}", hit,
                    f"hp={flyer.hp}")

    s, inp = settled_session()
    p = s.player
    p.inv = 999.0
    flyer = Flyer(p.x + 3.2, p.y, s.rng)
    s.enemies = [flyer]
    hp_sequence = []
    for _ in range(2):
        while p.attacking:
            advance(s, inp, 1)
        flyer.x, flyer.y = p.x + 3.2, p.y
        flyer.vx = flyer.vy = 0.0
        flyer.stun = 99.0
        hp_before = flyer.hp
        p.start_attack()
        for _ in range(30):
            advance(s, inp, 1)
            if flyer.hp < hp_before:
                break
        hp_sequence.append(flyer.hp)
        advance(s, inp, 20)
    ok &= check("flyer dies in 2 hits", hp_sequence == [1, 0] and not s.enemies,
                str(hp_sequence))
    return ok


def flyer_collision_test():
    print("Flyer tile collision:")
    s, inp = settled_session()
    p = s.player
    p.inv = 999.0
    flyer = Flyer(50.0, 16.0, s.rng)
    flyer.set_state(EnemyState.DIVE, config.ENEMY_DATA["flyer"]["attack_time"])
    flyer.dive_dx, flyer.dive_dy = 0.0, 1.0
    s.enemies = [flyer]

    touched_tile = False
    recovered_y = None
    for _ in range(120):
        advance(s, inp, 1)
        touched_tile |= collides(s.level, *flyer.rect)
        if flyer.state is EnemyState.RECOVER:
            recovered_y = flyer.y
            break

    ok = (
        not touched_tile
        and flyer.state is EnemyState.RECOVER
        and recovered_y is not None
        and recovered_y + flyer.h <= 21.0 + 1e-6
    )
    return check("dive stops on platform and enters RECOVER", ok,
                 f"state={flyer.state.value} bottom={flyer.y + flyer.h:.2f}")


def main():
    print("Emberfall M3 enemy tests")
    ok = data_tests()
    ok &= crawler_tests()
    ok &= flyer_float_test()
    ok &= flyer_state_sequence_test()
    ok &= flyer_contact_test()
    ok &= flyer_hit_test()
    ok &= flyer_collision_test()
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
