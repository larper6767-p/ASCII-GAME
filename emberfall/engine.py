"""Fixed-timestep engine loop and application state scaffolding."""
import enum

import pygame

from . import config
from .input import KeyboardInput
from .renderer import Renderer
from .session import GameSession


class GameState(enum.Enum):
    MENU = "menu"
    PLAYING = "playing"
    DEAD = "dead"
    WIN = "win"


class FixedStepper:
    """Accumulator-driven fixed updates, independent of render cadence."""

    def __init__(self, session, step=config.FIXED_DT):
        self.session = session
        self.step = step
        self.accumulator = 0.0
        self.steps = 0

    def advance(self, frame_dt, inp):
        frame_dt = min(frame_dt, config.MAX_FRAME_DT)
        self.accumulator += frame_dt
        count = 0
        while (self.accumulator >= self.step
               and count < config.MAX_STEPS_PER_FRAME):
            self.session.update(self.step, inp)
            inp.clear_edges()
            self.accumulator -= self.step
            self.steps += 1
            count += 1
        return count


class App:
    def __init__(self, render_fps=config.RENDER_FPS):
        pygame.init()
        self.renderer = Renderer()
        pygame.display.set_caption("Emberfall")
        self.clock = pygame.time.Clock()
        self.render_fps = render_fps
        self.session = GameSession()
        self.keyboard = KeyboardInput()
        self.stepper = FixedStepper(self.session)
        self.state = GameState.PLAYING
        self.running = True

        # Render one frame before the timed loop so glyph/light/parallax
        # caches are warm; it does not advance physics or change state.
        self.session.draw(self.renderer)
        self.renderer.flip()

    def process_events(self):
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
                self.renderer.toggle_overlay()
        self.keyboard.handle_events(events)

    def run(self):
        while self.running:
            frame_dt = self.clock.tick(self.render_fps) / 1000.0
            self.process_events()
            if self.state == GameState.PLAYING:
                self.stepper.advance(frame_dt, self.keyboard)
            # Real wall-clock frame time (includes pacing) for the F3 overlay.
            self.renderer.note_frame(frame_dt * 1000.0)
            self.session.draw(self.renderer)
            self.renderer.flip()
        pygame.quit()


def main():
    App().run()
