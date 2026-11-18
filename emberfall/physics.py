"""Axis-separated AABB movement against a Level's tile grid."""
import math

from .config import EPS


def overlap(a, b):
    """True when two (x, y, w, h) boxes overlap."""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def approach(value, target, step):
    """Move value toward target by at most step."""
    if value < target:
        return min(value + step, target)
    return max(value - step, target)


def collides(level, x, y, w, h):
    """Check the box against solid tiles in the level."""
    x0, x1 = math.floor(x), math.floor(x + w - EPS)
    y0, y1 = math.floor(y), math.floor(y + h - EPS)
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            if level.solid_at(tx, ty):
                return True
    return False


class Body:
    """A float-positioned AABB that collides with the tile grid."""

    def __init__(self, x, y, w, h):
        self.x = float(x)
        self.y = float(y)
        self.w = w
        self.h = h
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False

    @property
    def rect(self):
        return (self.x, self.y, self.w, self.h)

    def move(self, dt, level):
        """Move one axis at a time and snap to tile edges.

        Returns True if horizontal movement hit a wall this step.
        """
        hit_wall = False

        self.x += self.vx * dt
        if collides(level, self.x, self.y, self.w, self.h):
            if self.vx > 0:
                self.x = math.floor(self.x + self.w - EPS) - self.w
            else:
                self.x = math.floor(self.x) + 1
            self.vx = 0.0
            hit_wall = True

        self.y += self.vy * dt
        self.on_ground = False
        if collides(level, self.x, self.y, self.w, self.h):
            if self.vy > 0:
                self.y = math.floor(self.y + self.h - EPS) - self.h
                self.on_ground = True
            else:
                self.y = math.floor(self.y) + 1
            self.vy = 0.0

        return hit_wall
