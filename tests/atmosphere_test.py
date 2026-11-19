"""M6: per-room atmosphere, torch tiles, ambient embers and lock_on_enter.

Run from the repo root:

    python tests/atmosphere_test.py
"""
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from emberfall import config
from emberfall import physics
from emberfall.input import InputState
from emberfall.renderer import Renderer
from emberfall.rooms import RoomError, load_room, load_room_by_id
from emberfall.session import GameSession

CHECKS = 0
FAILURES = []


def check(name, condition, detail=""):
    global CHECKS
    CHECKS += 1
    if not condition:
        FAILURES.append(f"{name}: {detail}" if detail else name)


def _minimal_room(width=12, height=10, meta="spawn 1 1\n",
                  torch=(6, 3)):
    rows = []
    for y in range(height):
        if y in (0, height - 1):
            rows.append("#" * width)
        else:
            rows.append("#" + "." * (width - 2) + "#")
    if torch is not None:
        tx, ty = torch
        row = rows[ty]
        rows[ty] = row[:tx] + "T" + row[tx + 1:]
    return "\n".join(rows) + "\n---\n" + meta


def test_loader_atmosphere():
    print("Room atmosphere metadata:")
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        path = folder / "atmo.txt"
        path.write_text(_minimal_room(meta=(
            "atmosphere dusk\n"
            "palette #102030 #405060 #a0b0c0\n"
            "fog 0.25\n"
            "ember #ff8040\n"
            "lock_on_enter\n"
            "spawn 1 1\n"
        )), encoding="utf-8")
        room = load_room(path)
        atmosphere = room.atmosphere
        check("atmosphere name parsed", atmosphere["name"] == "dusk",
              atmosphere["name"])
        check("palette sky parsed", atmosphere["sky"] == (16, 32, 48),
              str(atmosphere["sky"]))
        check("palette rock parsed", atmosphere["rock"] == (64, 80, 96),
              str(atmosphere["rock"]))
        check("palette accent parsed", atmosphere["accent"] == (160, 176, 192),
              str(atmosphere["accent"]))
        check("fog density parsed", atmosphere["fog"] == 0.25,
              str(atmosphere["fog"]))
        check("ember colour parsed", atmosphere["ember"] == (255, 128, 64),
              str(atmosphere["ember"]))
        check("lock_on_enter parsed", room.lock_on_enter is True)
        check("torch tile parsed", room.tile_at(6, 3) == "T")
        check("torch tile is non-solid", not room.solid_at(6, 3))

        plain_path = folder / "plain.txt"
        plain_path.write_text(_minimal_room(meta="spawn 1 1\n"),
                              encoding="utf-8")
        plain = load_room(plain_path)
        check("plain room uses default atmosphere",
              plain.atmosphere["name"] == "default"
              and plain.atmosphere["fog"] == config.ATMO_FOG)
        check("plain room is not locked", plain.lock_on_enter is False)

        def expect(name, filename, meta_text, needle):
            p = folder / filename
            p.write_text(_minimal_room(meta=meta_text), encoding="utf-8")
            try:
                load_room(p)
            except RoomError as exc:
                check(name, needle in str(exc).lower(), str(exc))
            else:
                check(name, False, "no error raised")

        expect("loader rejects short palette", "badpalette.txt",
               "spawn 1 1\npalette #fff #000\n", "palette")
        expect("loader rejects bad fog number", "badfog.txt",
               "spawn 1 1\nfog nope\n", "number")
        expect("loader rejects out-of-range fog", "fogrange.txt",
               "spawn 1 1\nfog 1.5\n", "between")
        expect("loader rejects bad ember", "badember.txt",
               "spawn 1 1\nember zebra\n", "ember")
        expect("loader rejects nameless atmosphere", "badatmo.txt",
               "spawn 1 1\natmosphere\n", "atmosphere")
        expect("loader rejects lock arguments", "badlock.txt",
               "spawn 1 1\nlock_on_enter 1\n", "lock_on_enter")


def test_real_room_metadata():
    print("Real room atmosphere/lock data:")
    rooms = {rid: load_room_by_id(rid)
             for rid in ("room1", "room2", "room3")}
    check("room1 mood", rooms["room1"].atmosphere["name"] == "dusk",
          rooms["room1"].atmosphere["name"])
    check("room2 mood", rooms["room2"].atmosphere["name"] == "ruins",
          rooms["room2"].atmosphere["name"])
    check("room3 mood", rooms["room3"].atmosphere["name"] == "emberfall",
          rooms["room3"].atmosphere["name"])
    skies = {room.atmosphere["sky"] for room in rooms.values()}
    check("each room has a distinct sky palette", len(skies) == 3,
          str(skies))
    for rid, room in rooms.items():
        fog = room.atmosphere["fog"]
        check(f"{rid} fog in range", 0.0 <= fog <= 1.0, str(fog))
        torches = [
            (x, y) for y in range(room.height) for x in range(room.width)
            if room.tile_at(x, y) == "T"
        ]
        check(f"{rid} has torch tiles", len(torches) >= 3,
              str(len(torches)))
        check(f"{rid} torches are non-solid",
              all(not room.solid_at(x, y) for x, y in torches))
    check("room3 is the boss arena", rooms["room3"].lock_on_enter is True)
    check("room1 is not locked", rooms["room1"].lock_on_enter is False)
    check("room2 is not locked", rooms["room2"].lock_on_enter is False)


def test_atmosphere_rendering(renderer):
    print("Atmosphere, torches and ambient animation:")
    session = GameSession(seed=3, room_id="room1")
    session.draw(renderer)
    renderer.flip()

    check("room palette reached the renderer",
          renderer._atmosphere["name"] == "dusk",
          renderer._atmosphere["name"])
    rock = session.level.atmosphere["rock"]
    peak = max(rock)
    expected_tint = tuple(min(255, int(c * 255.0 / peak)) for c in rock)
    check("rock tint normalised", renderer._rock_tint == expected_tint,
          f"{renderer._rock_tint} vs {expected_tint}")
    check("parallax took the room palette",
          renderer.parallax.atmosphere_key is not None)

    # begin_frame clears to the room sky, not the global BG.
    renderer.begin_frame(0)
    sky = renderer.screen.get_at((0, 0))
    check("clear uses atmosphere sky",
          tuple(sky[:3]) == session.level.atmosphere["sky"],
          f"{tuple(sky[:3])} vs {session.level.atmosphere['sky']}")

    # The room's torch tiles are found and emit a client-side light.
    visible_torch = None
    for wx, wy in renderer._world_torches:
        if 0 <= wx < config.COLS:
            visible_torch = (wx, wy)
            break
    check("world torches precomputed", visible_torch is not None,
          str(renderer._world_torches))
    renderer.update_lighting(
        session.player, session.enemies, session.projectiles,
        0, 0.0, session.level,
    )
    layer = renderer.light_layer
    tx, ty = visible_torch
    lit = layer.level(int((tx + 0.5) * renderer.sub),
                      int((ty + 0.35) * renderer.sub))
    far = layer.level(renderer.sub_cols - 2, 4)
    check("torch emits light", lit > 160, str(lit))
    check("torch light falls off away from the flame", far < lit,
          f"far={far} torch={lit}")

    # Flicker is deterministic, animated and bounded.
    flickers = [
        renderer._torch_flicker(tx, ty, t)
        for t in (0.0, 0.013, 0.5, 1.0, 2.0, 7.5)
    ]
    check("torch flicker animates", len(set(flickers)) > 2,
          str(flickers))
    check("torch flicker stays bounded",
          all(0.35 <= value <= 1.25 for value in flickers), str(flickers))

    # Ambient motes use screen space, animate over time and never touch
    # simulation state.
    renderer.begin_frame(0)
    renderer.draw_ambient(0, 0.0)
    first = [pos for _surf, pos in renderer._fg_batch]
    check("ambient embers draw motes",
          len(first) == config.AMBIENT_EMBER_COUNT, str(len(first)))
    renderer.begin_frame(0)
    renderer.draw_ambient(0, 1.5)
    second = [pos for _surf, pos in renderer._fg_batch]
    check("ambient embers animate", first != second)
    check("ambient embers stay on screen",
          all(0 <= x < renderer.pixel_size[0]
              and 0 <= y < renderer.pixel_size[1] for x, y in second))

    # Animated colours are quantised before reaching the glyph cache, so a
    # long session must not accumulate one surface per frame per mote.
    cached_before = len(renderer.glyphs._surfaces)
    for frame in range(120):
        renderer.begin_frame(0)
        renderer.draw_ambient(0, frame * 0.05)
    cache_growth = len(renderer.glyphs._surfaces) - cached_before
    check("ambient glyph cache stays bounded", cache_growth < 220,
          f"{cache_growth} new surfaces")

    # Re-applying the same room must not rebuild the parallax layers.
    builds = renderer.parallax.build_count
    session.draw(renderer)
    renderer.flip()
    check("same room does not rebuild parallax",
          renderer.parallax.build_count == builds)

    # Entering another room re-tints everything once.
    session._enter_room("room2", "left")
    session.draw(renderer)
    renderer.flip()
    check("room change applies the new palette",
          renderer._atmosphere["name"] == "ruins",
          renderer._atmosphere["name"])
    check("room change rebuilds parallax",
          renderer.parallax.build_count == builds + 1,
          f"{builds} -> {renderer.parallax.build_count}")
    check("room change keeps physics untouched",
          session.room_id == "room2" and session.player.hp > 0)


def test_lock_on_enter():
    print("Boss-arena lock_on_enter:")
    session = GameSession(seed=4, room_id="room3")
    idle = InputState()
    check("boss room starts locked", session.room_locked)
    check("boss room has enemies", len(session.enemies) >= 3,
          str(len(session.enemies)))

    session.player.x = 1.0
    session.player.y = session.level.player_spawn[1]
    session.update(config.FIXED_DT, idle)
    check("locked room ignores the door", session.transition is None)

    # Killing the last enemy unlocks immediately (no reset needed).
    total = len(session.level.enemy_spawns)
    session.room_killed.setdefault("room3", set()).update(range(1, total))
    session.reset()
    check("one enemy remains", len(session.enemies) == 1,
          str(len(session.enemies)))
    check("boss room is still locked with one enemy", session.room_locked)

    enemy = session.enemies[0]
    enemy.hp = 1
    session.player.x = max(1.0, enemy.x - config.PLAYER_W)
    session.player.y = enemy.y
    session.player.facing = 1
    session.player.start_attack(False)
    for _ in range(14):
        session.update(config.FIXED_DT, idle)
        if not session.enemies:
            break
    check("last kill clears the room", not session.enemies)
    check("last kill unlocks the doors", not session.room_locked)

    session.player.x = 1.0
    session.player.y = session.level.player_spawn[1]
    # The final sword hit triggered hitstop, which delays the door check.
    for _ in range(12):
        session.player.x = 1.0
        session.update(config.FIXED_DT, idle)
        if session.transition is not None:
            break
    check("unlocked boss room door works",
          session.transition is not None
          and session.transition["dest"] == "room2",
          str(session.transition))


def test_sealed_room_failsafe():
    print("Sealed-arena soft-lock fail-safe:")
    idle = InputState()
    session = GameSession(seed=23, room_id="room3")
    total = len(session.level.enemy_spawns)
    survivor = session.enemies[0].spawn_index
    session.room_killed["room3"] = set(range(total)) - {survivor}
    session.reset()
    check("fail-safe room starts with one enemy",
          len(session.enemies) == 1 and session.room_locked)

    enemy = session.enemies[0]
    _, spawn_x, spawn_y = session.level.enemy_spawns[survivor]
    enemy.x = -20.0
    session._sealed_room_failsafe(config.FIXED_DT)
    check("escaped enemy is returned to its spawn",
          len(session.enemies) == 1
          and session.enemies[0].x == spawn_x
          and session.enemies[0].y == spawn_y,
          f"{session.enemies[0].x}, {session.enemies[0].y}")
    check("arena stays locked after one recovery", session.room_locked)

    enemy = session.enemies[0]
    enemy.x = -20.0
    session._sealed_room_failsafe(config.FIXED_DT)
    check("repeat escape removes the enemy", not session.enemies)
    check("removed enemy is recorded as defeated",
          survivor in session.room_killed["room3"])
    check("repeat escape unlocks the arena", not session.room_locked)

    # Embedding an enemy in a wall is unrecoverable: after the threshold it
    # is removed and counted as defeated so the door can unlock.
    session = GameSession(seed=24, room_id="room3")
    total = len(session.level.enemy_spawns)
    survivor = session.enemies[0].spawn_index
    session.room_killed["room3"] = set(range(total)) - {survivor}
    session.reset()
    enemy = session.enemies[0]
    enemy.x, enemy.y = 0.0, 0.0
    steps = int(config.LOCK_STUCK_SECONDS / config.FIXED_DT) + 2
    for _ in range(steps):
        session._sealed_room_failsafe(config.FIXED_DT)
        if not session.enemies:
            break
    check("stuck enemy is removed after the threshold", not session.enemies)
    check("stuck enemy is recorded as defeated",
          survivor in session.room_killed["room3"])
    check("stuck removal unlocks the arena", not session.room_locked)

    # A completely inactive enemy in a clear area gets one recovery then is
    # removed, so a frozen AI cannot seal the doors forever.
    session = GameSession(seed=27, room_id="room3")
    total = len(session.level.enemy_spawns)
    survivor = session.enemies[0].spawn_index
    session.room_killed["room3"] = set(range(total)) - {survivor}
    session.reset()
    session._sealed_room_failsafe(config.LOCK_IDLE_SECONDS + 0.1)
    check("inactive enemy gets a spawn recovery first",
          len(session.enemies) == 1)
    session._sealed_room_failsafe(config.LOCK_IDLE_SECONDS + 0.1)
    check("inactive enemy is removed on repeat timeout",
          not session.enemies and not session.room_locked)

    # No soft-lock: with the arena cleared, the door opens normally.
    session.player.x = 1.0
    session.player.y = session.level.player_spawn[1]
    session.update(config.FIXED_DT, idle)
    check("cleared arena door can start a transition",
          session.transition is not None
          and session.transition["dest"] == "room2",
          str(session.transition))


def test_locked_room_reentry():
    print("Re-entering a cleared locked room:")
    room = load_room_by_id("room3")
    total = len(room.enemy_spawns)
    session = GameSession(seed=25, room_id="room2")
    session.room_killed["room3"] = set(range(total))
    session._enter_room("room3", "left")
    check("re-entry has no enemies", not session.enemies)
    check("re-entry does not re-lock the cleared arena",
          session.room_locked is False)
    check("locked flag still describes the room",
          session.level.lock_on_enter is True)
    check("cleared arena arrival is safe",
          not any(physics.overlap(session.player.rect, enemy.rect)
                  for enemy in session.enemies)
          and not physics.collides(
              session.level, session.player.x, session.player.y,
              config.PLAYER_W, config.PLAYER_H,
          ))


def test_locked_room_death_reset():
    print("Dying inside the locked arena:")
    room = load_room_by_id("room3")
    total = len(room.enemy_spawns)
    session = GameSession(seed=26, room_id="room3")
    killed = {0, 1}
    session.room_killed["room3"] = set(killed)
    session.reset()
    check("arena locks with living enemies", session.room_locked)
    check("death setup keeps killed enemies dead",
          len(session.enemies) == total - len(killed))

    session.player.hp = 0
    session.update(config.FIXED_DT, InputState())
    check("death inside the arena stays in it", session.room_id == "room3")
    check("death respawns at full hp",
          session.player.hp == config.PLAYER_MAX_HP)
    check("death keeps the arena locked while enemies remain",
          session.room_locked)
    check("death respawns only the living enemies",
          len(session.enemies) == total - len(killed)
          and all(e.spawn_index not in killed for e in session.enemies))
    check("living enemies reset to their spawns",
          all((e.x, e.y) == session.level.enemy_spawns[e.spawn_index][1:]
              for e in session.enemies))
    check("death respawn is clear of solids and enemies",
          not physics.collides(
              session.level, session.player.x, session.player.y,
              config.PLAYER_W, config.PLAYER_H,
          )
          and not any(physics.overlap(session.player.rect, e.rect)
                      for e in session.enemies))
    check("death clears the previous projectiles",
          not session.projectiles.items)

    # A fully cleared arena stays unlocked through death/reset.
    session.room_killed["room3"] = set(range(total))
    session.reset()
    check("cleared arena is unlocked after reset", not session.room_locked)
    check("cleared arena has no respawned enemies", not session.enemies)


def test_atmosphere_physics_isolation(renderer):
    print("Atmosphere drawing stays out of physics:")

    def run(draw_frames):
        session = GameSession(seed=9, room_id="room3")
        inp = InputState()
        for i in range(36):
            inp.set_held(
                {"right", "jump"} if i % 4 == 0
                else {"right", "attack"} if i % 4 == 2
                else {"right"}
            )
            session.update(config.FIXED_DT, inp)
            inp.clear_edges()
            if draw_frames:
                session.draw(renderer)
                renderer.flip()
        return (
            session.time, session.player.x, session.player.y,
            session.player.vx, session.player.vy, session.player.hp,
            session.room_locked,
            [(e.kind, e.x, e.y, e.state_time) for e in session.enemies],
        )

    plain = run(False)
    drawn = run(True)
    check("atmosphere/torch/ember drawing does not change physics",
          plain == drawn,
          f"x {plain[1]:.6f} vs {drawn[1]:.6f}")


def test_atmosphere_frame_time(renderer):
    print("Atmosphere scene frame time (60 frames):")
    session = GameSession(seed=8, room_id="room3")
    inp = InputState()
    totals = []

    for i in range(80):
        inp.set_held(
            {"right"} if i % 5 else {"left", "attack"}
        )
        session.update(config.FIXED_DT, inp)
        inp.clear_edges()
        start = time.perf_counter()
        session.draw(renderer)
        renderer.flip()
        totals.append((time.perf_counter() - start) * 1000.0)

    warm = totals[20:]
    average = statistics.fmean(warm)
    p95 = statistics.quantiles(warm, n=20)[-1]
    worst = max(warm)
    print(f"  avg {average:.2f} ms | p95 {p95:.2f} | max {worst:.2f}")
    check("atmosphere average under 60 fps", average <= 16.67,
          f"{average:.2f} ms")
    check("atmosphere p95 stays sane", p95 <= 20.0,
          f"{p95:.2f} ms")


def main():
    print("Emberfall M6 atmosphere tests")
    pygame.init()
    try:
        renderer = Renderer(profile=True)
        test_loader_atmosphere()
        test_real_room_metadata()
        test_atmosphere_rendering(renderer)
        test_lock_on_enter()
        test_sealed_room_failsafe()
        test_locked_room_reentry()
        test_locked_room_death_reset()
        test_atmosphere_physics_isolation(renderer)
        test_atmosphere_frame_time(renderer)
    finally:
        pygame.quit()

    print(f"\n{CHECKS} checks, {len(FAILURES)} failures")
    for failure in FAILURES:
        print(f"  FAIL {failure}")
    if FAILURES:
        raise SystemExit(1)
    print("atmosphere tests passed")


if __name__ == "__main__":
    main()
