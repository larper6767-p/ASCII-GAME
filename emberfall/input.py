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
    pygame.K_SPACE: "jump",
    pygame.K_w: "jump",
    pygame.K_UP: "jump",
    pygame.K_z: "jump",
    pygame.K_j: "attack",
    pygame.K_x: "attack",
    pygame.K_r: "restart",
}


class InputState:
    """Held actions plus one-shot press/release edges."""

    def __init__(self):
        self.held = set()
        self.pressed = set()
        self.released = set()

    def set_held(self, actions):
        """Set held actions directly (used by tests and scripted input)."""
        actions = set(actions)
        self.pressed |= actions - self.held
        self.released |= self.held - actions
        self.held = actions

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
        return (1 if positive in self.held else 0) - (1 if negative in self.held else 0)


class KeyboardInput(InputState):
    """Tracks keys across events so sub-frame taps still produce an edge."""

    def __init__(self):
        super().__init__()
        self.keys_down = set()

    def handle_events(self, events):
        changed = False
        for event in events:
            if event.type == pygame.KEYDOWN and event.key in KEY_ACTIONS:
                if event.key not in self.keys_down:
                    self.keys_down.add(event.key)
                    changed = True
            elif event.type == pygame.KEYUP and event.key in KEY_ACTIONS:
                if event.key in self.keys_down:
                    self.keys_down.discard(event.key)
                    changed = True
            elif event.type == pygame.WINDOWFOCUSLOST:
                if self.keys_down:
                    self.keys_down.clear()
                    changed = True
        if changed:
            self.set_held({KEY_ACTIONS[key] for key in self.keys_down})

    def clear_all(self):
        self.keys_down.clear()
        self.set_held(set())
