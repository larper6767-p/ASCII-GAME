"""Gameplay session: owns the level, entities, combat resolution and drawing."""
import random

from . import combat, config, fx
from .entities import Player, create_enemy
from .input import InputState
from .physics import overlap
from .projectiles import ProjectileSystem
from .world import Camera, build_demo_level


class GameSession:
    def __init__(self, seed=7, level=None):
        self.rng = random.Random(seed)
        self.level = level if level is not None else build_demo_level(self.rng)
        self.time = 0.0
        self.player = None
        self.enemies = []
        self.projectiles = None
        self.particles = None
        self.camera = None
        self.hitstop = None
        self.shake = None
        self.reset()

    def reset(self):
        """Respawn the player and enemies. World time keeps running."""
        px, py = self.level.player_spawn
        self.player = Player(px, py)
        self.enemies = [create_enemy(kind, x, y, self.rng)
                        for kind, x, y in self.level.enemy_spawns]
        self.projectiles = ProjectileSystem()
        self.particles = fx.Particles(self.rng)
        self.camera = Camera(config.COLS, self.level.width)
        self.hitstop = combat.HitStop()
        self.shake = fx.ScreenShake()

    def update(self, dt, inp: InputState):
        # Input edges are handled before hit-stop, matching the starter.
        if inp.was_pressed("restart"):
            self.reset()
        if inp.was_pressed("jump"):
            self.player.jump_buf = config.JUMP_BUFFER_TIME
        if inp.was_pressed("attack"):
            # Down + attack is a pogo only while airborne.
            self.player.start_attack(inp.is_held("down"))

        self.shake.update(dt)
        if self.hitstop.active:
            self.hitstop.update(dt)
            return

        self.time += dt
        p = self.player
        move_axis = inp.axis("left", "right")
        p.update(dt, self.level, move_axis, inp.is_held("jump"))

        for enemy in self.enemies:
            enemy.update(dt, self.level, p, self.projectiles)

        # Sword hits, resolved before contact damage. Enemy state never
        # prevents damage, so every enemy can be hit during any windup.
        attack_box = combat.attack_hitbox(p)
        if attack_box is not None:
            for enemy in list(self.enemies):
                if enemy not in p.hit_set and overlap(attack_box, enemy.rect):
                    p.hit_set.add(enemy)
                    combat.damage_enemy(enemy, p.facing)
                    if p.pogo:
                        p.pogo_bounce()
                    self.hitstop.trigger(config.SWORD_HITSTOP)
                    self.shake.trigger(config.HIT_SHAKE)
                    enemy.hit_burst(self.particles)
                    if enemy.hp <= 0:
                        enemy.death_burst(self.particles)
                        self.enemies.remove(enemy)

        # Projectiles: moving shots never interact with the sword.
        self.projectiles.update(dt, self.level)
        projectile = self.projectiles.pop_overlap(p.rect)
        if projectile is not None and p.inv <= 0.0:
            self._hurt_player(p, projectile.x, projectile.damage)

        # Contact damage. Each type declares which states are dangerous.
        if p.inv <= 0.0:
            for enemy in self.enemies:
                if (enemy.contact_damage_enabled
                        and overlap(p.rect, enemy.rect)):
                    self._hurt_player(
                        p, enemy.x, enemy.data["contact_damage"])
                    break

        if p.hp <= 0:
            self.reset()
            return

        self.particles.update(dt, self.level)

        target = p.x + p.w / 2.0 - config.COLS / 2.0
        self.camera.update(target, dt)

    def _hurt_player(self, player, source_x, damage):
        combat.damage_player(player, source_x, damage)
        self.hitstop.trigger(config.HURT_HITSTOP)
        self.shake.trigger(config.HURT_SHAKE)
        self.particles.burst(
            player.x + 1.5, player.y + 1.5, 14,
            config.PLAYER_HURT_PARTICLE_COLORS,
        )

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw(self, renderer):
        p = self.player
        ox = self.camera.offset + self.shake.x_offset()
        renderer.begin_frame(ox)
        renderer.draw_parallax(ox, self.time)
        renderer.update_lighting(
            p, self.enemies, self.projectiles, ox
        )
        renderer.draw_terrain(self.level, ox, self.time, p)
        renderer.draw_enemies(self.enemies, ox)
        renderer.draw_player(p, ox, self.time)
        renderer.draw_projectiles(self.projectiles, ox)
        renderer.draw_slash(p, ox)
        renderer.draw_particles(self.particles, ox)
        renderer.draw_hud(p, self.enemies)
        renderer.end_frame()
