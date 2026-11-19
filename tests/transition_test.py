"""M5: room loading, persistent room state, door fades and frame times.

Run from the repo root:

    python tests/transition_test.py
"""
import os
import statistics
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from emberfall import config
from emberfall import physics
from emberfall.input import InputState
from emberfall.renderer import Renderer
from emberfall.rooms import load_room_by_id
from emberfall.session import GameSession

CHECKS = 0
FAILURES = []

LEGEND_CHARS = set('#=". ')


def check(name, condition, detail=""):
    global CHECKS
    CHECKS += 1
    if not condition:
        FAILURES.append(f"{name}: {detail}" if detail else name)


def step(session, renderer, frames, dt=config.FIXED_DT, inp=None):
    """Advance and draw; return per-frame wall-clock times in milliseconds."""
    inp = inp if inp is not None else InputState()
    times = []
    for _ in range(frames):
        start = time.perf_counter()
        session.update(dt, inp)
        inp.clear_edges()
        session.draw(renderer)
        renderer.flip()
        times.append((time.perf_counter() - start) * 1000.0)
    return times


def test_room_files():
    rooms = {rid: load_room_by_id(rid)
             for rid in ("room1", "room2", "room3")}
    for rid, room in rooms.items():
        check(f"{rid} id", room.id == rid, room.id)
        check(f"{rid} size", room.width >= 100 and room.height == 28,
              f"{room.width}x{room.height}")
        check(f"{rid} solid floor",
              room.solid_at(room.width // 2, room.height - 1))
        check(f"{rid} open sky", not room.solid_at(room.width // 2, 2))
        check(f"{rid} spawn present", room.player_spawn[1] > 0)
        check(f"{rid} enemies", len(room.enemy_spawns) >= 3,
              str(len(room.enemy_spawns)))
        bad = {char for row in room.tiles for char in row} - LEGEND_CHARS
        check(f"{rid} legend chars", not bad, repr(bad))

    check("room1 exits right",
          any(d["dest"] == "room2" and d["side"] == "right"
              for d in rooms["room1"].doors))
    check("room2 connects both ways", len(rooms["room2"].doors) == 2)
    check("room3 exits left",
          any(d["dest"] == "room2" and d["side"] == "left"
              for d in rooms["room3"].doors))

    for room in rooms.values():
        for door in room.doors:
            x, y, w, h = door["rect"]
            check(f"{room.id} door on floor",
                  y + h == room.height - 3, str(door["rect"]))
            check(f"{room.id} door inside room",
                  0 <= x and x + w <= room.width)

        px, py = room.player_spawn
        check(f"{room.id} spawn clear",
              not physics.collides(room, px, py,
                                   config.PLAYER_W, config.PLAYER_H),
              f"({px}, {py})")
        for index, (kind, ex, ey) in enumerate(room.enemy_spawns):
            data = config.ENEMY_DATA[kind]
            check(f"{room.id} enemy {index} clear",
                  not physics.collides(room, ex, ey, data["w"], data["h"]),
                  f"{kind} ({ex}, {ey})")
    return rooms


def test_persistence():
    session = GameSession(seed=11, room_id="room1")
    total = len(session.enemies)
    check("room1 starts with enemies", total >= 3, str(total))

    # Kill one enemy: it must stay dead across a player-death reset.
    session.room_killed.setdefault("room1", set()).add(0)
    session.reset()
    check("killed enemy stays dead after reset",
          len(session.enemies) == total - 1, str(len(session.enemies)))
    check("killed set survives reset",
          0 in session.room_killed.get("room1", set()))

    # A full restart brings it back.
    session.restart()
    check("restart revives enemies", len(session.enemies) == total,
          str(len(session.enemies)))
    check("restart clears killed set", not session.room_killed)

    # Persistence is per room and survives leaving and returning.
    session = GameSession(seed=11, room_id="room1")
    room1_total = len(session.enemies)
    session.room_killed.setdefault("room1", set()).add(1)
    session.room_id = "room2"
    session.level = load_room_by_id("room2")
    session.reset()
    room2_total = len(session.enemies)
    session.room_killed.setdefault("room2", set()).add(0)
    check("room2 kill tracked",
          0 in session.room_killed.get("room2", set()))
    session.room_id = "room1"
    session.level = load_room_by_id("room1")
    session.reset()
    check("room1 keeps its own kills",
          len(session.enemies) == room1_total - 1,
          str(len(session.enemies)))
    check("room2 kill not leaked into room1",
          1 in session.room_killed.get("room1", set()))
    session.room_id = "room2"
    session.level = load_room_by_id("room2")
    session.reset()
    check("room2 keeps its own kills",
          len(session.enemies) == room2_total - 1,
          str(len(session.enemies)))


def test_transition_flow(renderer):
    session = GameSession(seed=11, room_id="room1")
    session.player.x = session.level.width - 2.0
    session.player.y = session.level.player_spawn[1]
    idle = InputState()

    session.update(config.FIXED_DT, idle)
    check("walking into door starts transition", session.transition is not None)
    check("transition starts faded out",
          session.transition is not None
          and session.transition["phase"] == "out")
    check("physics frozen while fading",
          session.player.x >= session.level.width - 2.0)

    old_level = session.level
    switched = False
    for _ in range(60):
        session.update(config.FIXED_DT, idle)
        if session.transition is not None and session.transition["phase"] == "in":
            switched = True
            break
    check("transition reaches fade-in", switched)
    check("room switched", session.room_id == "room2", str(session.room_id))
    check("destination level loaded", session.level is not old_level)
    check("spawned near left edge", 2.0 < session.player.x < 12.0,
          str(session.player.x))
    check("cache warm queued", session._pending_cache_warm is not None)
    check("door cooldown armed", session._door_cooldown > 0.0)

    session.draw(renderer)
    check("cache warm consumed in fade",
          session._pending_cache_warm is None)

    for _ in range(60):
        session.update(config.FIXED_DT, idle)
        if session.transition is None:
            break
    check("transition finishes", session.transition is None)

    # Walking back through the left door returns to room1.
    session.player.x = 1.0
    session.player.y = session.level.player_spawn[1]
    session.update(config.FIXED_DT, idle)
    for _ in range(60):
        session.update(config.FIXED_DT, idle)
        if session.room_id == "room1":
            break
    check("left door returns to room1", session.room_id == "room1",
          str(session.room_id))


def test_transition_frame_time():
    renderer = Renderer(profile=False)
    session = GameSession(seed=11, room_id="room1")
    idle = InputState()

    # Warm the room1 caches before the measured run.
    step(session, renderer, 4)
    baseline = step(session, renderer, 30)
    baseline_median = statistics.median(baseline)

    # Walk into the right door, then measure across the whole fade.
    session.player.x = session.level.width - 2.0
    session.player.y = session.level.player_spawn[1]

    measured = []
    in_transition = []
    post = []
    for _ in range(90):
        start = time.perf_counter()
        session.update(config.FIXED_DT, idle)
        session.draw(renderer)
        renderer.flip()
        ms = (time.perf_counter() - start) * 1000.0
        measured.append(ms)
        if session.transition is not None:
            in_transition.append(ms)
        else:
            post.append(ms)

    check("frame-time run transitioned", session.room_id == "room2",
          str(session.room_id))
    check("fade frames observed", len(in_transition) >= 6,
          str(len(in_transition)))

    fade_max = max(in_transition) if in_transition else 0.0
    post_median = statistics.median(post) if post else 0.0
    post_p95 = (statistics.quantiles(post, n=20)[-1]
                if len(post) >= 20 else max(post or [0.0]))
    post_max = max(post) if post else 0.0

    print(f"  baseline median {baseline_median:.2f} ms")
    print(f"  fade max        {fade_max:.2f} ms")
    print(f"  post median     {post_median:.2f} ms")
    print(f"  post p95        {post_p95:.2f} ms")
    print(f"  post max        {post_max:.2f} ms")

    # The fade may absorb the cache rebuild, but it must stay bounded and the
    # frames after the fade must not spike relative to normal play.
    check("fade build bounded", fade_max <= 80.0, f"{fade_max:.2f} ms")
    check("post-transition median sane",
          post_median <= max(baseline_median * 2.0, 8.0),
          f"{post_median:.2f} ms vs {baseline_median:.2f} ms")
    check("post-transition p95 under 60 fps", post_p95 <= 16.67,
          f"{post_p95:.2f} ms")
    check("no post-transition spike", post_max <= 33.0,
          f"{post_max:.2f} ms")


def main():
    pygame.init()
    renderer = Renderer(profile=False)

    test_room_files()
    test_persistence()
    test_transition_flow(renderer)
    test_transition_frame_time()

    print(f"{CHECKS} checks, {len(FAILURES)} failures")
    for failure in FAILURES:
        print(f"  FAIL {failure}")
    if FAILURES:
        raise SystemExit(1)
    print("transition tests passed")


if __name__ == "__main__":
    main()
