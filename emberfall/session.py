"""Gameplay session: owns the level, entities, combat resolution and drawing."""
import random

from . import combat, config, fx
from .entities import Player, create_enemy
from .input import InputState
from .physics import overlap
from .projectiles import ProjectileSystem
from .rooms import load_room_by_id
from .world import Camera, build_demo_level


class GameSession:
    def __init__(self, seed=7, level=None, room_id=None):
        self.rng = random.Random(seed)
        if room_id is not None:
            self.room_id = room_id
            self.level = load_room_by_id(room_id)
        elif level is not None:
            self.room_id = None
            self.level = level
        else:
            self.room_id = None
            self.level = build_demo_level(self.rng)
        self.time = 0.0
        self.player = None
        self.enemies = []
        self.projectiles = None
        self.particles = None
        self.camera = None
        self.hitstop = None
        self.shake = None
        # Per-room persistent state: room id -> dead enemy spawn indices.
        # Kills survive room changes and player deaths, and are only cleared
        # by a full restart (R key / new session).
        self.room_killed = {}
        self.transition = None
        self._pending_cache_warm = None
        self._door_cooldown = 0.0
        self.reset()

    def _dead_here(self):
        return self.room_killed.setdefault(self.room_id, set())

    def _spawn_enemies(self):
        dead = self.room_killed.get(self.room_id, ())
        self.enemies = []
        for index, (kind, x, y) in enumerate(self.level.enemy_spawns):
            if index in dead:
                continue
            enemy = create_enemy(kind, x, y, self.rng)
            enemy.spawn_index = index
            self.enemies.append(enemy)

    def reset(self):
        """Respawn the player and (non-killed) enemies. World time keeps running."""
        px, py = self.level.player_spawn
        self.player = Player(px, py)
        self._spawn_enemies()
        self.projectiles = ProjectileSystem()
        self.particles = fx.Particles(self.rng)
        self.camera = Camera(config.COLS, self.level.width)
        self.hitstop = combat.HitStop()
        self.shake = fx.ScreenShake()

    def restart(self):
        """Full restart: cleared killed-enemy state, then reset."""
        self.room_killed.clear()
        self.transition = None
        self._pending_cache_warm = None
        self._door_cooldown = 0.0
        self.reset()

    def _check_doors(self):
        if self.transition is not None or self._door_cooldown > 0.0:
            return
        doors = getattr(self.level, "doors", None)
        if not doors:
            return
        p = self.player
        for door in doors:
            r = door["rect"]
            if (p.x < r[0] + r[2] and p.x + p.w > r[0]
                    and p.y < r[1] + r[3] and p.y + p.h > r[1]):
                self._start_transition(door)
                break

    def _start_transition(self, door):
        self.transition = {
            "dest": door["dest"],
            "dest_side": door["dest_side"],
            "phase": "out",
            "t": 0.0,
            "duration": 0.30,
        }

    def _spawn_for_side(self, side, level):
        # Spawn a few cells inside the edge so the player does not overlap
        # the door trigger again on arrival.
        if side == "left":
            return (4.0, level.player_spawn[1])
        if side == "right":
            return (level.width - 5.0, level.player_spawn[1])
        if side == "top":
            return (level.player_spawn[0], 2.0)
        if side == "bottom":
            return (level.player_spawn[0], level.height - 4.0)
        return level.player_spawn

    def _finish_transition(self):
        t = self.transition
        self.room_id = t["dest"]
        self.level = load_room_by_id(t["dest"])
        spawn = self._spawn_for_side(t["dest_side"], self.level)
        self.player = Player(*spawn)
        self.player.inv = 0.6
        self._spawn_enemies()
        self.projectiles = ProjectileSystem()
        self.particles = fx.Particles(self.rng)
        self.camera = Camera(config.COLS, self.level.width)
        # Place the camera immediately so the first frame is not a lurch.
        target = self.player.x + self.player.w / 2.0 - config.COLS / 2.0
        max_x = max(0.0, self.level.width - config.COLS)
        self.camera.x = max(0.0, min(max_x, target))
        self.hitstop = combat.HitStop()
        self.shake = fx.ScreenShake()
        self._pending_cache_warm = (self.level, self.camera.offset)
        self._door_cooldown = 0.5
        # Switch to fade-in.
        self.transition["phase"] = "in"
        self.transition["t"] = 0.0

    def _update_transition(self, dt):
        t = self.transition
        t["t"] += dt
        half = t["duration"] / 2.0
        if t["phase"] == "out" and t["t"] >= half:
            self._finish_transition()
            return
        if t["phase"] == "in" and t["t"] >= half:
            self.transition = None

    def update(self, dt, inp: InputState):
        # Input edges are handled before hit-stop, matching the starter.
        if inp.was_pressed("restart"):
            self.restart()
            return
        if self.transition is not None:
            self._update_transition(dt)
            return

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
        if self._door_cooldown > 0.0:
            self._door_cooldown = max(0.0, self._door_cooldown - dt)
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
                        if getattr(enemy, "spawn_index", None) is not None:
                            self._dead_here().add(enemy.spawn_index)
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

        self._check_doors()

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

        # Warm the destination room's caches during the fade so the first
        # post-transition frame does not spike.
        if self._pending_cache_warm is not None:
            level, warm_ox = self._pending_cache_warm
            renderer.prepare_room(level, warm_ox)
            self._pending_cache_warm = None

        renderer.begin_frame(ox)
        renderer.draw_parallax(ox, self.time)
        renderer.update_lighting(
            p, self.enemies, self.projectiles, ox
        )
        renderer.draw_terrain(self.level, ox, self.time, p)
        renderer.draw_doors(self.level, ox, self.time)
        renderer.draw_enemies(self.enemies, ox)
        renderer.draw_player(p, ox, self.time)
        renderer.draw_projectiles(self.projectiles, ox)
        renderer.draw_slash(p, ox)
        renderer.draw_particles(self.particles, ox)
        renderer.draw_hud(p, self.enemies)
        renderer.end_frame()

        # Fade overlay on top of everything during a transition.
        if self.transition is not None:
            t = self.transition
            half = t["duration"] / 2.0
            if t["phase"] == "out":
                progress = min(1.0, t["t"] / max(0.001, half))
            else:
                progress = max(0.0, 1.0 - (t["t"] / max(0.001, half)))
            alpha = int(255 * progress)
            renderer.draw_fade(alpha)
