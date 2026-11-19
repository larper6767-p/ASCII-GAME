"""Input abstraction and rebindable key configuration.

Key bindings live in ``assets/keybinds.json``. Edit that file (or point the
``EMBERFALL_KEYBINDS`` environment variable at another JSON file) and restart
the game to rebind. Every action needs at least one key::

    {
      "left": ["a", "left"],
      "right": ["d", "right"],
      "down": ["s", "down"],
      "jump": ["space", "w", "z", "up", "k"],
      "attack": ["j"],
      "restart": ["r"],
      "weapon_sword": ["1"],
      "weapon_bow": ["2"],
      "weapon_gun": ["3"]
    }

The three weapon actions are optional for backward compatibility: a custom
file without them still works, and the slime simply stays on the sword form.
Key names are SDL/pygame names such as ``space``, ``left``, ``f4`` or a
single character. Core game logic never reads pygame directly.

Edges are latched until a fixed step consumes them, so a tap that happens
between physics steps is never lost. ``frame_pressed``/``frame_released``
retain edges for the F4 debug overlay until the frame has been drawn.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parents[1]
KEYBINDS_PATH = ROOT / "assets" / "keybinds.json"
REQUIRED_ACTIONS = ("left", "right", "down", "jump", "attack", "restart")
OPTIONAL_ACTIONS = ("weapon_sword", "weapon_bow", "weapon_gun")
ALLOWED_ACTIONS = REQUIRED_ACTIONS + OPTIONAL_ACTIONS

# Used only when the default config file is missing. The file remains the
# source of truth for a normal checkout so bindings are editable without code.
FALLBACK_KEYBINDS = {
    "left": ["a", "left"],
    "right": ["d", "right"],
    "down": ["s", "down"],
    "jump": ["space", "w", "z", "up", "k"],
    "attack": ["j"],
    "restart": ["r"],
    "weapon_sword": ["1"],
    "weapon_bow": ["2"],
    "weapon_gun": ["3"],
}


class KeybindError(ValueError):
    """Raised when the keybind file is missing, malformed or ambiguous."""


def _key_code(name):
    """Resolve an SDL/pygame key name to a pygame key code."""
    text = str(name).strip().lower()
    if not text:
        raise KeybindError("empty key name")
    if text in ("enter",):
        text = "return"
    if text in ("esc",):
        text = "escape"
    if len(text) == 1:
        return ord(text)

    aliases = {
        "ctrl": pygame.K_LCTRL,
        "control": pygame.K_LCTRL,
        "shift": pygame.K_LSHIFT,
        "alt": pygame.K_LALT,
        "page_up": pygame.K_PAGEUP,
        "page_down": pygame.K_PAGEDOWN,
        "pgup": pygame.K_PAGEUP,
        "pgdn": pygame.K_PAGEDOWN,
    }
    if text in aliases:
        return aliases[text]
    code = getattr(pygame, f"K_{text.upper()}", None)
    if code is not None:
        return code
    raise KeybindError(f"unknown key name {name!r}")


def keybinds_path():
    """Return the active keybind file; respects ``EMBERFALL_KEYBINDS``."""
    override = os.environ.get("EMBERFALL_KEYBINDS")
    if override:
        return Path(override).expanduser()
    return KEYBINDS_PATH


def load_keybinds(path=None):
    """Load and validate a keybind JSON file, returning {key_code: action}."""
    override = os.environ.get("EMBERFALL_KEYBINDS")
    explicit = path is not None or bool(override)
    source = Path(path).expanduser() if path is not None else keybinds_path()
    if not source.exists():
        if explicit:
            raise KeybindError(f"{source}: keybind file not found")
        raw = FALLBACK_KEYBINDS
    else:
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise KeybindError(
                f"{source.name}: invalid JSON at line {exc.lineno}: {exc.msg}"
            ) from exc
        except OSError as exc:
            raise KeybindError(f"{source}: cannot read: {exc}") from exc

    if not isinstance(raw, dict):
        raise KeybindError(f"{source.name}: expected an object of action -> keys")
    extra = sorted(set(raw) - set(ALLOWED_ACTIONS))
    missing = [action for action in REQUIRED_ACTIONS if action not in raw]
    if extra:
        raise KeybindError(f"{source.name}: unknown actions: {', '.join(extra)}")
    if missing:
        raise KeybindError(
            f"{source.name}: missing actions: {', '.join(missing)}"
        )

    actions = {}
    used = {}
    for action in ALLOWED_ACTIONS:
        if action not in raw:
            continue
        names = raw[action]
        if isinstance(names, str):
            names = [names]
        if not isinstance(names, list) or not names:
            raise KeybindError(
                f"{source.name}: {action} needs a non-empty list of key names"
            )
        for name in names:
            if not isinstance(name, str):
                raise KeybindError(
                    f"{source.name}: {action} contains a non-string key name"
                )
            code = _key_code(name)
            previous = used.get(code)
            if previous is not None and previous != action:
                raise KeybindError(
                    f"{source.name}: {name!r} is bound to both "
                    f"{previous!r} and {action!r}"
                )
            used[code] = action
            actions[code] = action
    return actions


KEY_ACTIONS = load_keybinds()


def reload_keybinds():
    """Reload the module-level bindings (used after editing the config)."""
    global KEY_ACTIONS
    KEY_ACTIONS = load_keybinds()
    return KEY_ACTIONS


class InputState:
    """Held actions plus one-shot press/release edges.

    Movement is read from held actions. Opposite directions use
    last-pressed-wins, which is tracked separately from the action set so
    keyboard and test input behave the same way.

    ``frame_pressed`` and ``frame_released`` are debug-only accumulators. They
    are not consumed by the fixed step, so the F4 overlay can show every edge
    that arrived during a rendered frame.
    """

    def __init__(self):
        self.held = set()
        self.pressed = set()
        self.released = set()
        self.frame_pressed = set()
        self.frame_released = set()
        self._press_order = []

    def set_held(self, actions):
        """Set held actions directly (used by tests and scripted input)."""
        actions = set(actions)
        newly_pressed = actions - self.held
        newly_released = self.held - actions
        self.pressed |= newly_pressed
        self.released |= newly_released
        self.frame_pressed |= newly_pressed
        self.frame_released |= newly_released
        self.held = actions

        self._press_order = [action for action in self._press_order
                             if action in actions]
        # A single call cannot express which of two simultaneous presses
        # happened first; use a stable order for that tie.
        for action in sorted(newly_pressed):
            self._mark_newest(action)

    def _mark_newest(self, action):
        """Move an action to the end of the last-pressed order."""
        if action in self._press_order:
            self._press_order.remove(action)
        self._press_order.append(action)

    def clear_edges(self):
        self.pressed.clear()
        self.released.clear()

    def clear_debug_edges(self):
        """Clear per-render-frame edges after the F4 overlay is drawn."""
        self.frame_pressed.clear()
        self.frame_released.clear()

    def latched_edges(self):
        """All jump/attack-style edges not yet shown by the debug overlay."""
        return self.pressed | self.frame_pressed

    def is_held(self, action):
        return action in self.held

    def was_pressed(self, action):
        return action in self.pressed

    def was_released(self, action):
        return action in self.released

    def axis(self, negative, positive):
        """Return -1/0/1; when both are held the newer press wins."""
        neg_held = negative in self.held
        pos_held = positive in self.held
        if neg_held and pos_held:
            if negative in self._press_order and positive in self._press_order:
                newer = self._press_order.index(positive) > self._press_order.index(negative)
                return 1 if newer else -1
            return 1 if positive > negative else -1
        return int(pos_held) - int(neg_held)


class KeyboardInput(InputState):
    """Tracks keys across events so sub-frame taps still produce an edge.

    All physical keys are tracked for the raw-key debug view; only keys in
    ``key_actions`` feed game actions.
    """

    def __init__(self, key_actions=None):
        super().__init__()
        self.key_actions = dict(KEY_ACTIONS if key_actions is None
                                else key_actions)
        self.keys_down = set()
        self.key_order = []

    def raw_key_names(self):
        """Human-readable names of held physical keys, oldest press first."""
        names = []
        for key in self.key_order:
            try:
                names.append(pygame.key.name(key) or str(key))
            except (ValueError, pygame.error):
                names.append(str(key))
        return names

    def _sync_held(self):
        self.set_held({self.key_actions[key] for key in self.keys_down
                       if key in self.key_actions})

    def axis(self, negative, positive):
        # Physical key order makes WASD/arrow mixes fully last-pressed-wins,
        # including duplicate keys for the same direction.
        for key in reversed(self.key_order):
            action = self.key_actions.get(key)
            if action == negative:
                return -1
            if action == positive:
                return 1
        return super().axis(negative, positive)

    def handle_events(self, events):
        # Apply each event in order so opposite-direction presses in the same
        # frame still resolve to the last key pressed.
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key not in self.keys_down:
                    self.keys_down.add(event.key)
                    self.key_order.append(event.key)
                    if event.key in self.key_actions:
                        self._sync_held()
            elif event.type == pygame.KEYUP:
                if event.key in self.keys_down:
                    self.keys_down.discard(event.key)
                    if event.key in self.key_order:
                        self.key_order.remove(event.key)
                    if event.key in self.key_actions:
                        self._sync_held()
            elif event.type == pygame.WINDOWFOCUSLOST:
                self.keys_down.clear()
                self.key_order.clear()
                self._sync_held()

    def clear_all(self):
        self.keys_down.clear()
        self.key_order.clear()
        self.set_held(set())
