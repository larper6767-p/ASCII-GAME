"""M7 boss tests: state machine, phase change, persistence and rendering.

Run from the repo root with ``python tests/boss_test.py``. No pytest needed.
"""
import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame

pygame.init()

from emberfall import config, physics
from emberfall.boss import Boss, BossState
from emberfall.entities import Player
from emberfall.input import InputState
from emberfall.projectiles import ProjectileSystem
from emberfall.renderer import Renderer
from emberfall.session import GameSession
from emberfall.world import Level

DT = config.FIXED_DT
CHECKS = 0
FAILURES = []


def check(name, condition, detail=""):
    global CHECKS
    CHECKS += 1
    if not condition:
        FAILURES.append(f"{name}: {detail}" if detail else name)


def arena():
    """A flat arena with the floor top at row 16."""
    width, height = 70, 20
    rows = ["." * width for _ in range(16)] + ["#" * width for _ in range(4)]
    return Level(rows, [], (10.0, 13.0))


def make_boss(seed=7, x=20.0, y=12.0):
    return Boss(x, y, random.Random(seed))


def first_order(states):
    """Deduplicate consecutive states, preserving transition order."""
    order = []
    for state in states:
        if not order or order[-1] is not state:
            order.append(state)
    return order


def advance(boss, level, player, projectiles, predicate, limit=1200):
    states = []
    for _ in range(limit):
        boss.update(DT, level, player, projectiles)
        states.append(boss.state)
        if predicate():
            break
    return states


def test_data_and_intro():
    print("Boss data and invulnerable intro:")
    data = config.BOSS_DATA
    check("boss stats live in BOSS_DATA", isinstance(data, dict))
    check("boss room loader sees the boss",
          "boss" in config.ENEMY_DATA and config.ENEMY_DATA["boss"] is data)
    check("boss has all three attacks",
          set(data["attack_choices"]) == {"slam", "charge", "rain"})
    check("boss has a minimum recovery window", data["min_recovery"] > 0.0)

    boss = make_boss()
    level = arena()
    player = Player(10.0, 13.0)
    check("boss starts in the intro", boss.state is BossState.INTRO)
    check("intro is visibly different", boss.color == data["intro_color"])
    check("intro is invulnerable", boss.invulnerable)
    hp = boss.hp
    killed = boss.take_hit(1)
    check("intro hit does not damage the boss",
          boss.hp == hp and not killed)

    projectiles = ProjectileSystem()
    advance(boss, level, player, projectiles,
            lambda: boss.state is BossState.IDLE)
    check("intro ends in idle", boss.state is BossState.IDLE)
    check("boss is vulnerable after the intro", not boss.invulnerable)
    check("boss faces the player", boss.facing == -1)
    boss.take_hit(1)
    check("post-intro hits reduce hp", boss.hp == hp - 1)

    # The session also has to respect the intro gate, not only take_hit.
    session = GameSession(seed=11, room_id="room3")
    intro_boss = session.enemies[0]
    intro_hp = intro_boss.hp
    session.player.x = intro_boss.x - config.PLAYER_W
    session.player.y = intro_boss.y
    session.player.facing = 1
    session.player.start_attack(False)
    for _ in range(20):
        session.update(DT, InputState())
    check("session attacks cannot damage the intro boss",
          intro_boss.hp == intro_hp and intro_boss.invulnerable)


def test_slam_order_and_shockwaves():
    print("Slam ordering and floor shockwaves:")
    boss = make_boss(seed=3)
    level = arena()
    player = Player(40.0, 13.0)
    projectiles = ProjectileSystem()
    boss.set_state(BossState.IDLE, 10.0)
    boss._begin_attack("slam", level, player)
    check("slam starts in windup",
          boss.state is BossState.SLAM_WINDUP and boss.telegraph)

    states = []
    recovery = None
    for _ in range(1200):
        boss.update(DT, level, player, projectiles)
        states.append(boss.state)
        if boss.state is BossState.SLAM_RECOVER and recovery is None:
            recovery = boss.state_duration
        if boss.state is BossState.IDLE and BossState.SLAM_ACTIVE in states:
            break
    check("slam completes its state machine",
          boss.state is BossState.IDLE, str(first_order(states)))
    check("slam state order is windup-active-recover-idle",
          first_order(states) == [
              BossState.SLAM_WINDUP,
              BossState.SLAM_ACTIVE,
              BossState.SLAM_RECOVER,
              BossState.IDLE,
          ], str(first_order(states)))
    check("slam active spawns two shockwaves",
          len(projectiles.items) == 2,
          str([(p.kind, p.vx) for p in projectiles.items]))
    waves = [p for p in projectiles.items if p.kind == "shockwave"]
    check("shockwaves travel outward",
          len(waves) == 2
          and {1 for p in waves if p.vx > 0}
          and {-1 for p in waves if p.vx < 0})
    check("shockwaves are floor-height hazards",
          all(p.y == boss.y + boss.h - config.BOSS_DATA["slam_wave_h"]
              for p in waves))
    check("slam recovery meets the minimum",
          recovery is not None
          and recovery >= config.BOSS_DATA["min_recovery"],
          str(recovery))


def test_charge_locks_direction():
    print("Locked-direction charge:")
    boss = make_boss(seed=4)
    level = arena()
    player = Player(50.0, 13.0)
    projectiles = ProjectileSystem()
    boss.set_state(BossState.IDLE, 10.0)
    boss._begin_attack("charge", level, player)
    states = [boss.state]
    check("charge starts in windup", boss.state is BossState.CHARGE_WINDUP)
    check("charge direction locks at windup", boss.charge_dir == 1)

    # Move through the player during the windup; the aim must not change.
    player.x = 2.0
    states.extend(advance(boss, level, player, projectiles,
                          lambda: boss.state is BossState.CHARGE))
    check("charge direction survives player movement",
          boss.charge_dir == 1)
    boss.update(DT, level, player, projectiles)
    states.append(boss.state)
    check("charge moves in the locked direction", boss.vx > 0.0,
          f"vx={boss.vx:.2f}")
    player.x = 60.0
    boss.update(DT, level, player, projectiles)
    states.append(boss.state)
    check("charge does not retarget during the dash", boss.vx > 0.0,
          f"vx={boss.vx:.2f}")

    states.extend(advance(boss, level, player, projectiles,
                          lambda: boss.state is BossState.CHARGE_RECOVER))
    recovery = boss.state_duration
    check("charge recovery meets the minimum",
          recovery >= config.BOSS_DATA["min_recovery"], str(recovery))
    states.extend(advance(boss, level, player, projectiles,
                          lambda: boss.state is BossState.IDLE))
    check("charge returns to idle", boss.state is BossState.IDLE)
    check("charge state order is windup-charge-recover-idle",
          first_order(states) == [
              BossState.CHARGE_WINDUP,
              BossState.CHARGE,
              BossState.CHARGE_RECOVER,
              BossState.IDLE,
          ], str(first_order(states)))


def test_rain_warnings_and_rng():
    print("Ember rain warnings, embers and seeded RNG:")
    level = arena()
    player = Player(40.0, 13.0)
    boss = make_boss(seed=9)
    boss.set_state(BossState.IDLE, 10.0)
    boss._begin_attack("rain", level, player)
    states = [boss.state]
    check("rain starts in windup", boss.state is BossState.RAIN_WINDUP)
    check("rain creates floor warning marks",
          len(boss.warnings) == config.BOSS_DATA["rain_count"],
          str(len(boss.warnings)))
    check("warning marks sit on the floor",
          all(w["y"] == 16.0 for w in boss.warnings),
          str([w["y"] for w in boss.warnings]))
    check("the first warning is under the player",
          abs(boss.warnings[0]["x"] - 41.5) < 1e-9)

    projectiles = ProjectileSystem()
    states.extend(advance(boss, level, player, projectiles,
                          lambda: boss.state is BossState.RAIN_ACTIVE))
    check("warnings survive into the active rain",
          len(boss.warnings) == config.BOSS_DATA["rain_count"])
    states.extend(advance(boss, level, player, projectiles,
                          lambda: boss.state is BossState.RAIN_RECOVER))
    recovery = boss.state_duration
    embers = [p for p in projectiles.items if p.kind == "ember"]
    check("rain spawns all ember projectiles",
          len(embers) == config.BOSS_DATA["rain_count"],
          str(len(embers)))
    check("embers fall straight down",
          all(p.vx == 0.0 and p.vy > 0.0 for p in embers))
    check("rain clears its floor warnings",
          not boss.warnings)
    check("rain recovery meets the minimum",
          recovery >= config.BOSS_DATA["min_recovery"], str(recovery))
    states.extend(advance(boss, level, player, projectiles,
                          lambda: boss.state is BossState.IDLE))
    check("rain state order is windup-active-recover-idle",
          first_order(states) == [
              BossState.RAIN_WINDUP,
              BossState.RAIN_ACTIVE,
              BossState.RAIN_RECOVER,
              BossState.IDLE,
          ], str(first_order(states)))

    # Two identical seeds produce identical warning layouts. No global RNG
    # is consulted, so this also works with other enemies in a session.
    a = make_boss(seed=123)
    b = make_boss(seed=123)
    c = make_boss(seed=124)
    a._make_warnings(level, player)
    b._make_warnings(level, player)
    c._make_warnings(level, player)
    check("same seed gives the same rain layout",
          a.warnings == b.warnings)
    check("different seeds vary the rain layout",
          a.warnings != c.warnings)

    session_a = GameSession(seed=77, room_id="room3")
    session_b = GameSession(seed=77, room_id="room3")
    check("session seed drives the boss attack choice",
          session_a.enemies[0]._choose_attack()
          == session_b.enemies[0]._choose_attack())


def test_phase_change_and_combo():
    print("Phase change at half HP and chained combo:")
    boss = make_boss(seed=5)
    level = arena()
    player = Player(40.0, 13.0)
    projectiles = ProjectileSystem()
    boss.set_state(BossState.IDLE, 10.0)
    base_color = boss.color
    boss.hp = boss.max_hp // 2 + 1
    boss.take_hit(1)
    check("half HP starts the phase change",
          boss.phase_two and boss.state is BossState.PHASE_CHANGE)
    check("phase change changes the visible colour",
          boss.color != base_color, str(boss.color))
    check("phase change queues a chained combo",
          boss.combo_queue == list(config.BOSS_DATA["phase_combo"]),
          str(boss.combo_queue))

    states = advance(boss, level, player, projectiles,
                     lambda: boss.state is BossState.SLAM_WINDUP)
    check("phase change chains into the first combo attack",
          boss.state is BossState.SLAM_WINDUP)
    check("phase transition did not idle before the combo",
          BossState.IDLE not in first_order(states),
          str(first_order(states)))
    advance(boss, level, player, projectiles,
            lambda: boss.state is BossState.SLAM_RECOVER)
    check("combo slam recovery meets the minimum",
          boss.state_duration >= config.BOSS_DATA["min_recovery"])
    advance(boss, level, player, projectiles,
            lambda: boss.state is BossState.RAIN_WINDUP)
    check("combo continues into ember rain",
          boss.state is BossState.RAIN_WINDUP)
    advance(boss, level, player, projectiles,
            lambda: boss.state is BossState.RAIN_RECOVER)
    check("combo rain recovery meets the minimum",
          boss.state_duration >= config.BOSS_DATA["min_recovery"])
    advance(boss, level, player, projectiles,
            lambda: boss.state is BossState.IDLE)
    check("combo ends in idle after the chained attacks",
          boss.state is BossState.IDLE and not boss.combo_queue)


def test_boss_health_bar_and_warnings_draw():
    print("Boss health bar and warning rendering:")
    session = GameSession(seed=31, room_id="room3")
    renderer = Renderer()
    boss = session.enemies[0]
    renderer.begin_frame(0)
    renderer.draw_hud(session.player, session.enemies, session.room_locked)
    bar_width = min(520, renderer._screen_size[0] - 40)
    check("boss health bar panel is drawn",
          any(surface.get_size() == (bar_width, 56)
              for surface, _pos in renderer._fg_batch),
          str([surface.get_size() for surface, _p in renderer._fg_batch]))
    check("health bar title includes the boss name",
          "Ember Warden" in boss.name)

    boss.warnings = [{"x": 40.0, "y": 16.0, "delay": 0.0, "fired": False}]
    renderer.begin_frame(0)
    renderer.draw_boss_warnings([boss], 0, 0.0)
    check("floor warning marks submit glyphs",
          len([1 for _s, _p in renderer._fg_batch]) >= 3)

    renderer.begin_frame(0)
    renderer.draw_enemies([boss], 0)
    check("boss art submits its glyphs",
          len(renderer._fg_batch) >= 90,
          str(len(renderer._fg_batch)))
    from emberfall import sprites as ascii_sprites
    check("boss art rows are the expected size",
          all(len(row) == 18 for row in ascii_sprites.BOSS_FRAME))


def test_defeat_unlock_and_persistence():
    print("Boss defeat unlocks and persists:")
    session = GameSession(seed=41, room_id="room3")
    boss = session.enemies[0]
    spawn_index = boss.spawn_index
    boss.set_state(BossState.IDLE, 1.0)
    boss.hp = 1
    session.player.x = max(1.0, boss.x - config.PLAYER_W)
    session.player.y = boss.y
    session.player.facing = 1
    session.player.start_attack(False)
    for _ in range(30):
        session.update(DT, InputState())
        if not session.enemies:
            break
    check("boss dies from the final sword hit", not session.enemies)
    check("boss defeat unlocks the doors immediately",
          not session.room_locked)
    check("boss defeat is recorded persistently",
          spawn_index in session.room_killed.get("room3", set()))

    session.player.x = 1.0
    session.player.y = session.level.player_spawn[1]
    for _ in range(20):
        session.player.x = 1.0
        session.update(DT, InputState())
        if session.transition is not None:
            break
    check("defeated boss room door starts a transition",
          session.transition is not None
          and session.transition["dest"] == "room2")

    reentry = GameSession(seed=42, room_id="room2")
    reentry.room_killed["room3"] = {spawn_index}
    reentry._enter_room("room3", "left")
    check("defeated boss does not respawn on re-entry",
          not reentry.enemies)
    check("cleared boss room stays unlocked",
          not reentry.room_locked)

    # Death inside the arena resets the living boss, not its defeat.
    death = GameSession(seed=43, room_id="room3")
    living = death.enemies[0]
    living.x = 60.0
    death.player.hp = 0
    death.update(DT, InputState())
    check("death respawns the living boss",
          len(death.enemies) == 1
          and death.enemies[0].spawn_index == 0)
    check("death restores the boss to its spawn",
          (death.enemies[0].x, death.enemies[0].y)
          == death.level.enemy_spawns[0][1:])
    check("death keeps the arena locked while the boss lives",
          death.room_locked)


def test_no_soft_lock_failsafe():
    print("Boss-arena no-soft-lock fail-safe:")
    session = GameSession(seed=51, room_id="room3")
    boss = session.enemies[0]
    spawn = session.level.enemy_spawns[0][1:]
    boss.x = -80.0
    session._sealed_room_failsafe(DT)
    check("escaped boss returns to its spawn",
          len(session.enemies) == 1
          and (session.enemies[0].x, session.enemies[0].y) == spawn)
    check("arena remains locked after one boss recovery", session.room_locked)
    boss = session.enemies[0]
    boss.x = -80.0
    session._sealed_room_failsafe(DT)
    check("repeat boss escape removes it", not session.enemies)
    check("removed boss unlocks the arena", not session.room_locked)
    check("removed boss is persistently defeated",
          0 in session.room_killed.get("room3", set()))
    check("cleared arena has no solid overlap at spawn",
          not physics.collides(
              session.level, session.player.x, session.player.y,
              config.PLAYER_W, config.PLAYER_H,
          ))


def main():
    print("Emberfall M7 boss tests")
    test_data_and_intro()
    test_slam_order_and_shockwaves()
    test_charge_locks_direction()
    test_rain_warnings_and_rng()
    test_phase_change_and_combo()
    test_boss_health_bar_and_warnings_draw()
    test_defeat_unlock_and_persistence()
    test_no_soft_lock_failsafe()
    print(f"\n{CHECKS} checks, {len(FAILURES)} failures")
    for failure in FAILURES:
        print(f"  FAIL {failure}")
    if FAILURES:
        print("boss tests failed")
        return 1
    print("boss tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
