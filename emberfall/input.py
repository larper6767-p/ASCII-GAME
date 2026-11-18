"""Input abstraction. Core game logic never reads pygame directly.

Edges are latched until a fixed step consumes them, so a tap that happens
between physics steps is never lost.
"""
import pygame


KEY_ACTIONS = {
    pygame.K_a: "left",
    pygame.K_LEFT: "left",
    pygame.K_d: "right",
    pygame.K_RIGHT: "right",
    pygame.K_s: "down",
    pygame.K_DOWN: "down",
    pygame.K_SPACE: "jump",
    pygame.K_w: "jump",
    pygame.K_UP: "jump",
    pygame.K_z: "jump",
    pygame.K_j: "attack",
    pygame.K_x: "attack",
    pygame.K_r: "restart",
}


class InputState:
    """Held actions plus one-shot press/release edges.

    Movement is read from held actions. Opposite directions use
    last-pressed-wins, which is tracked separately from the action set so
    keyboard and test input behave the same way.
    """

    def __init__(self):
        self.held = set()
        self.pressed = set()
        self.released = set()
        self._press_order = []

    def set_held(self, actions):
        """Set held actions directly (used by tests and scripted input)."""
        actions = set(actions)
        newly_pressed = actions - self.held
        self.pressed |= newly_pressed
        self.released |= self.held - actions
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
    """Tracks keys across events so sub-frame taps still produce an edge."""

    def __init__(self):
        super().__init__()
        self.keys_down = set()
        self.key_order = []

    def _sync_held(self):
        self.set_held({KEY_ACTIONS[key] for key in self.keys_down})

    def axis(self, negative, positive):
        # Physical key order makes WASD/arrow mixes fully last-pressed-wins,
        # including duplicate keys for the same direction.
        for key in reversed(self.key_order):
            action = KEY_ACTIONS[key]
            if action == negative:
                return -1
            if action == positive:
                return 1
        return super().axis(negative, positive)

    def handle_events(self, events):
        # Apply each event in order so opposite-direction presses in the same
        # frame still resolve to the last key pressed.
        for event in events:
            if event.type == pygame.KEYDOWN and event.key in KEY_ACTIONS:
                if event.key not in self.keys_down:
                    self.keys_down.add(event.key)
                    self.key_order.append(event.key)
                    self._sync_held()
            elif event.type == pygame.KEYUP and event.key in KEY_ACTIONS:
                if event.key in self.keys_down:
                    self.keys_down.discard(event.key)
                    if event.key in self.key_order:
                        self.key_order.remove(event.key)
                    self._sync_held()
            elif event.type == pygame.WINDOWFOCUSLOST:
                if self.keys_down:
                    self.keys_down.clear()
                    self.key_order.clear()
                    self._sync_held()

    def clear_all(self):
        self.keys_down.clear()
        self.key_order.clear()
        self.set_held(set())
