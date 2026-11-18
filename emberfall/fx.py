"""Particles, grass animation and screen shake."""
import math
import random

from . import config


class Particle:
    def __init__(self, x, y, vx, vy, life, char, color):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.char = char
        self.color = color


class Particles:
    def __init__(self, rng):
        self.rng = rng
        self.items = []

    def clear(self):
        self.items.clear()

    def burst(self, x, y, count, colors, speed=14.0):
        for _ in range(count):
            angle = self.rng.uniform(0.0, math.tau)
            magnitude = self.rng.uniform(0.3, 1.0) * speed
            self.items.append(Particle(
                x,
                y,
                math.cos(angle) * magnitude * 1.6,
                math.sin(angle) * magnitude - 4.0,
                self.rng.uniform(0.3, 0.7),
                self.rng.choice("*'.,+x"),
                self.rng.choice(colors),
            ))

    def update(self, dt, level):
        alive = []
        for p in self.items:
            p.life -= dt
            p.vy += config.PARTICLE_GRAVITY * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            if p.life > 0.0 and not level.solid_at(int(p.x), int(p.y)):
                alive.append(p)
        self.items = alive


def grass_char(wx, wy, player, time):
    """Return (char, color) for a grass tile, bending away from the player."""
    wind = math.sin(time * config.GRASS_WIND_SPEED + wx * 0.35) * 0.7
    px = player.x + player.w / 2
    py = player.y + player.h
    dx = wx - px
    if abs(dx) < config.GRASS_BEND_DISTANCE and abs(wy - py) < 4:
        wind += math.copysign(
            1.2 * (1.0 - abs(dx) / config.GRASS_BEND_DISTANCE), dx
        )
    tall = (wx * 7 + wy) % 3 != 0
    if tall:
        char = "\\" if wind < -0.35 else "/" if wind > 0.35 else "|"
    else:
        char = "`" if wind < -0.35 else "'" if wind > 0.35 else ","
    shade = 120 + (wx * 37) % 80
    return char, (50, shade, 60)


class ScreenShake:
    """Visual-only camera jolt. Uses its own RNG so render cadence cannot
    change simulation randomness."""

    def __init__(self):
        self.time = 0.0
        self._rng = random.Random(1337)

    def trigger(self, seconds):
        self.time = seconds

    def update(self, dt):
        self.time = max(0.0, self.time - dt)

    def x_offset(self):
        if self.time <= 0.0:
            return 0
        return self._rng.choice((-1, 0, 1)) * config.SHAKE_CELLS
