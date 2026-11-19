"""Input regression tests: rebindable keys, jump latching and the F4 panel.

Run from the repo root with ``python tests/input_test.py``. No pytest needed.
"""
import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame

pygame.init()

from emberfall import config
from emberfall.input import (
    KEY_ACTIONS,
    KeyboardInput,
    KeybindError,
    load_keybinds,
)
from emberfall.renderer import Renderer
from emberfall.session import GameSession
from emberfall.world import Level

CHECKS = 0
FAILURES = []


def check(name, condition, detail=""):
    global CHECKS
    CHECKS += 1
    if not condition:
        FAILURES.append(f"{name}: {detail}" if detail else name)


def flat_level():
    """A wide, empty floor so movement/jump tests never touch a wall."""
    width, height = 40, 14
    rows = []
    for y in range(height):
        rows.append("#" * width if y >= 12 else "." * width)
    return Level(rows, [], player_spawn=(5.0, 9.0))


def key_event(event_type, key):
    return pygame.event.Event(event_type, key=key)


def settled_session():
    session = GameSession(seed=41, level=flat_level())
    idle = KeyboardInput()
    for _ in range(6):
        session.update(config.FIXED_DT, idle)
    return session


def test_default_keybinds():
    print("Default keybinds:")
    check("K is a default jump key", KEY_ACTIONS[pygame.K_k] == "jump")
    for key, name in (
        (pygame.K_SPACE, "space"),
        (pygame.K_w, "w"),
        (pygame.K_z, "z"),
        (pygame.K_UP, "up"),
    ):
        check(f"{name} still jumps", KEY_ACTIONS[key] == "jump")
    check("J is attack", KEY_ACTIONS[pygame.K_j] == "attack")
    check("X is not a default attack", pygame.K_x not in KEY_ACTIONS)
    check("S and Down are pogo directions",
          KEY_ACTIONS[pygame.K_s] == "down"
          and KEY_ACTIONS[pygame.K_DOWN] == "down")
    check("A/D and arrows are movement",
          KEY_ACTIONS[pygame.K_a] == "left"
          and KEY_ACTIONS[pygame.K_d] == "right"
          and KEY_ACTIONS[pygame.K_LEFT] == "left"
          and KEY_ACTIONS[pygame.K_RIGHT] == "right")

    path = ROOT / "assets" / "keybinds.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    check("config file exists and is JSON", isinstance(raw, dict))
    check("config jump list keeps K and old keys",
          raw["jump"] == ["space", "w", "z", "up", "k"])
    check("config attack is J", raw["attack"] == ["j"])


def test_custom_keybinds():
    print("Rebindable key files:")
    custom = {
        "left": ["a"],
        "right": ["d"],
        "down": ["s"],
        "jump": ["q"],
        "attack": ["u"],
        "restart": ["r"],
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "keys.json"
        path.write_text(json.dumps(custom), encoding="utf-8")
        binds = load_keybinds(path)
        check("custom jump key loads", binds[pygame.K_q] == "jump")
        check("custom attack key loads", binds[pygame.K_u] == "attack")
        keyboard = KeyboardInput(binds)
        keyboard.handle_events([key_event(pygame.KEYDOWN, pygame.K_q)])
        check("custom keyboard emits the jump edge",
              keyboard.was_pressed("jump")
              and keyboard.axis("left", "right") == 0)
        keyboard.handle_events([key_event(pygame.KEYUP, pygame.K_q)])
        check("custom keyboard releases the jump action",
              not keyboard.is_held("jump"))

        path.write_text(json.dumps({**custom, "attack": ["q"]}),
                        encoding="utf-8")
        try:
            load_keybinds(path)
            duplicate_ok = False
        except KeybindError:
            duplicate_ok = True
        check("duplicate key across actions is rejected", duplicate_ok)

        path.write_text(json.dumps({**custom, "jump": ["not-a-key"]}),
                        encoding="utf-8")
        try:
            load_keybinds(path)
            unknown_ok = False
        except KeybindError:
            unknown_ok = True
        check("unknown key name is rejected", unknown_ok)

        path.write_text(json.dumps({**custom, "jump": []}), encoding="utf-8")
        try:
            load_keybinds(path)
            empty_ok = False
        except KeybindError:
            empty_ok = True
        check("empty action binding is rejected", empty_ok)


def test_alternating_jump_keys():
    print("Alternating A/D plus every jump key in one step:")
    jump_keys = [
        (pygame.K_SPACE, "space"),
        (pygame.K_w, "w"),
        (pygame.K_z, "z"),
        (pygame.K_UP, "up"),
        (pygame.K_k, "k"),
    ]
    for jump_key, label in jump_keys:
        for first, second, want_axis, direction_name in (
            (pygame.K_a, pygame.K_d, 1, "A->D"),
            (pygame.K_d, pygame.K_a, -1, "D->A"),
        ):
            session = settled_session()
            keyboard = KeyboardInput()
            keyboard.handle_events([key_event(pygame.KEYDOWN, first)])
            check(f"{label} {direction_name}: first direction held",
                  keyboard.axis("left", "right") == (-1 if first == pygame.K_a else 1))
            session.update(config.FIXED_DT, keyboard)
            keyboard.clear_edges()

            keyboard.handle_events([
                key_event(pygame.KEYDOWN, second),
                key_event(pygame.KEYDOWN, jump_key),
            ])
            check(f"{label} {direction_name}: direction changes in the "
                  "same latched step",
                  keyboard.axis("left", "right") == want_axis,
                  str(keyboard.axis("left", "right")))
            check(f"{label} {direction_name}: jump edge is latched",
                  "jump" in keyboard.latched_edges())

            session.update(config.FIXED_DT, keyboard)
            player = session.player
            check(f"{label} {direction_name}: jump fires",
                  player.vy < 0.0,
                  f"vy={player.vy:.2f} on_ground={player.on_ground}")
            check(f"{label} {direction_name}: direction stayed latched "
                  "through the jump step",
                  player.facing == want_axis,
                  f"facing={player.facing}")


def test_attack_and_pogo():
    print("J attack and S/Down + J pogo:")
    session = settled_session()
    keyboard = KeyboardInput()
    keyboard.handle_events([key_event(pygame.KEYDOWN, pygame.K_j)])
    session.update(config.FIXED_DT, keyboard)
    check("J starts an attack", session.player.attacking)
    check("ground J is not a pogo", not session.player.pogo)

    for down_key, label in ((pygame.K_s, "S"), (pygame.K_DOWN, "Down")):
        session = settled_session()
        session.player.y -= 4.0
        session.player.on_ground = False
        session.player.coyote = 0.0
        session.player.vy = 0.0
        keyboard = KeyboardInput()
        keyboard.handle_events([
            key_event(pygame.KEYDOWN, down_key),
            key_event(pygame.KEYDOWN, pygame.K_j),
        ])
        session.update(config.FIXED_DT, keyboard)
        check(f"{label}+J starts a pogo attack",
              session.player.attacking and session.player.pogo)


def test_f4_debug_overlay():
    print("F4 raw input overlay:")
    renderer = Renderer()
    check("F4 starts disabled", not renderer.input_debug_enabled)
    check("F4 toggles on", renderer.toggle_input_debug())
    check("F4 toggles off", not renderer.toggle_input_debug())
    renderer.toggle_input_debug()

    session = settled_session()
    # Keep the player airborne so the jump buffer remains armed after the
    # step; this is exactly the state the overlay is meant to expose.
    session.player.on_ground = False
    session.player.coyote = 0.0
    session.player.y -= 4.0
    keyboard = KeyboardInput()
    keyboard.handle_events([
        key_event(pygame.KEYDOWN, pygame.K_a),
        key_event(pygame.KEYDOWN, pygame.K_k),
        key_event(pygame.KEYDOWN, pygame.K_j),
    ])
    session.update(config.FIXED_DT, keyboard)

    renderer.capture_input_debug(keyboard, session)
    lines = "\n".join(renderer.input_debug_lines)
    check("F4 shows raw held keys",
          "raw keys:" in lines and "a" in lines and "k" in lines,
          lines)
    check("F4 shows latched jump and attack edges",
          "jump=YES" in lines and "attack=YES" in lines, lines)
    check("F4 shows the jump buffer was set",
          "jump buffer: SET" in lines, lines)
    check("F4 shows ground/coyote state", "ground: no" in lines, lines)

    renderer.begin_frame(camera_offset=0)
    renderer.draw_input_debug()
    check("F4 panel is submitted to the renderer",
          len(renderer._fg_batch) > 0)
    renderer.flush()


def main():
    print("Emberfall input tests")
    test_default_keybinds()
    test_custom_keybinds()
    test_alternating_jump_keys()
    test_attack_and_pogo()
    test_f4_debug_overlay()
    print(f"\n{CHECKS} checks, {len(FAILURES)} failures")
    for failure in FAILURES:
        print(f"  FAIL {failure}")
    if FAILURES:
        print("input tests failed")
        return 1
    print("input tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
