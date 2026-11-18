"""Gameplay session: owns the level, entities, combat resolution and drawing."""
import random

from . import combat, config, fx, sprites
from .entities import Crawler, Player
from .input import InputState
from .physics import overlap
from .world import Camera, build_demo_level


class GameSession:
    def __init__(self, seed=7, level=None):
        self.rng = random.Random(seed)
        self.level = level if level is not None else build_demo_level(self.rng)
        self.time = 0.0
        self.player = None
        self.enemies = []
        self.particles = None
        self.camera = None
        self.hitstop = None
        self.shake = None
        self.reset()

    def reset(self):
        """Respawn the player and enemies. World time keeps running."""
        px, py = self.level.player_spawn
        self.player = Player(px, py)
        self.enemies = [Crawler(x, y, self.rng) for x, y in self.level.enemy_spawns]
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
            self.player.start_attack()  # ignored while stunned or already swinging

        self.shake.update(dt)
        if self.hitstop.active:
            self.hitstop.update(dt)
            return

        self.time += dt
        p = self.player
        move_axis = inp.axis("left", "right")
        p.update(dt, self.level, move_axis, inp.is_held("jump"))

        for enemy in self.enemies:
            enemy.update(dt, self.level)

        # Sword hits, resolved before contact damage.
        attack_box = combat.attack_hitbox(p)
        if attack_box is not None:
            for enemy in list(self.enemies):
                if enemy not in p.hit_set and overlap(attack_box, enemy.rect):
                    p.hit_set.add(enemy)
                    combat.damage_enemy(enemy, p.facing)
                    self.hitstop.trigger(config.SWORD_HITSTOP)
                    self.shake.trigger(config.HIT_SHAKE)
                    self.particles.burst(
                        enemy.x + 1.5, enemy.y + 1.0, 8,
                        config.HIT_PARTICLE_COLORS,
                    )
                    if enemy.hp <= 0:
                        self.particles.burst(
                            enemy.x + 1.5, enemy.y + 1.0, 25,
                            config.DEATH_PARTICLE_COLORS, speed=20.0,
                        )
                        self.enemies.remove(enemy)

        # Contact damage.
        if p.inv <= 0.0:
            for enemy in self.enemies:
                if overlap(p.rect, enemy.rect):
                    combat.damage_player(p, enemy.x)
                    self.hitstop.trigger(config.HURT_HITSTOP)
                    self.shake.trigger(config.HURT_SHAKE)
                    self.particles.burst(
                        p.x + 1.5, p.y + 1.5, 14,
                        config.PLAYER_HURT_PARTICLE_COLORS,
                    )
                    break

        if p.hp <= 0:
            self.reset()
            return

        self.particles.update(dt, self.level)

        target = p.x + p.w / 2.0 - config.COLS / 2.0
        self.camera.update(target, dt)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw(self, renderer):
        renderer.clear(config.BG)
        p = self.player
        ox = self.camera.offset + self.shake.x_offset()

        for sy in range(config.ROWS):
            for sx in range(config.COLS):
                wx = ox + sx
                tile = self.level.tile_at(wx, sy)
                if tile == "#":
                    v = 70 + ((wx * 7 + sy * 13) % 3) * 12
                    renderer.put(sx, sy, "#", (v, v, v + 10))
                elif tile == "=":
                    renderer.put(sx, sy, "=", (170, 120, 70))
                elif tile == '"':
                    char, color = fx.grass_char(wx, sy, p, self.time)
                    renderer.put(sx, sy, char, color)

        for enemy in self.enemies:
            color = config.WHITE if enemy.flash > 0.0 else config.ENEMY_COLOR
            renderer.put_sprite(enemy.sprite(), enemy.x, enemy.y, color, ox)

        if p.inv <= 0.0 or int(p.inv * 20) % 2 == 0:
            renderer.put_sprite(p.sprite(), p.x, p.y, config.PLAYER_COLOR, ox)

        if p.attacking and p.attack_t >= config.ATTACK_STARTUP:
            slash = sprites.SLASH if p.facing > 0 else sprites.mirror(sprites.SLASH)
            if p.facing > 0:
                bx = p.x + p.w
            else:
                bx = p.x - config.ATTACK_REACH
            if p.attack_t < config.ATTACK_ACTIVE_END:
                color = (255, 255, 200)
            else:
                color = (130, 130, 110)
            renderer.put_sprite(slash, bx, p.y, color, ox)

        for particle in self.particles.items:
            renderer.put(int(particle.x) - ox, int(particle.y),
                         particle.char, particle.color)

        renderer.put_text(
            2, 1,
            "HP [" + "#" * p.hp + "-" * (p.max_hp - p.hp) + "]",
            config.HUD_HEALTH_COLOR,
        )
        renderer.put_text(
            2, 2,
            "A/D move  SPACE jump  J attack  R restart",
            config.HUD_HELP_COLOR,
        )
        if not self.enemies:
            renderer.put_text(
                config.COLS // 2 - 8, 6,
                "ALL ENEMIES SLAIN",
                config.HUD_CLEAR_COLOR,
            )
