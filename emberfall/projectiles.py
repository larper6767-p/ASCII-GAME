"""Reusable projectile entities and the per-session projectile list.

Enemy types spawn projectiles through ProjectileSystem. Later bosses can use
the same system with their own speed, damage, size and appearance.
"""
import math

from . import config
from .physics import collides, overlap


class Projectile:
    """A small moving hitbox that dies on solid tiles or after its lifetime."""

    def __init__(self, x, y, vx, vy, damage=1, color=config.WHITE, char="*",
                 w=1, h=1, lifetime=None):
        self.x = float(x)
        self.y = float(y)
        self.w = w
        self.h = h
        self.vx = float(vx)
        self.vy = float(vy)
        self.damage = damage
        self.color = color
        self.char = char
        self.lifetime = config.PROJECTILE_LIFETIME if lifetime is None else lifetime
        self.alive = True

    @property
    def rect(self):
        return (self.x, self.y, self.w, self.h)

    def update(self, dt, level):
        if not self.alive:
            return
        self.lifetime -= dt
        if self.lifetime <= 0.0:
            self.alive = False
            return
        if collides(level, *self.rect):
            self.alive = False
            return

        # Substep so future fast boss projectiles cannot tunnel through a
        # one-cell wall between two fixed updates.
        travel = math.hypot(self.vx, self.vy) * dt
        substeps = max(1, int(math.ceil(travel / 0.5)))
        step_dt = dt / substeps
        for _ in range(substeps):
            self.x += self.vx * step_dt
            self.y += self.vy * step_dt
            if collides(level, *self.rect):
                self.alive = False
                return


class ProjectileSystem:
    def __init__(self):
        self.items = []

    def clear(self):
        self.items.clear()

    def spawn(self, x, y, vx, vy, damage=1, color=config.WHITE, char="*",
              w=1, h=1, lifetime=None):
        projectile = Projectile(
            x, y, vx, vy,
            damage=damage, color=color, char=char,
            w=w, h=h, lifetime=lifetime,
        )
        self.items.append(projectile)
        return projectile

    def update(self, dt, level):
        for projectile in self.items:
            projectile.update(dt, level)
        self.items = [projectile for projectile in self.items if projectile.alive]

    def pop_overlap(self, box):
        """Remove and return the first projectile touching a world AABB."""
        for projectile in self.items:
            if overlap(projectile.rect, box):
                self.items.remove(projectile)
                return projectile
        return None
