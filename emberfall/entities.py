"""Player and enemy entities. AI is a small explicit state machine per type."""
import enum
import math

from . import config, sprites
from .physics import Body, approach


class Player(Body):
    def __init__(self, x, y):
        super().__init__(x, y, config.PLAYER_W, config.PLAYER_H)
        self.facing = 1
        self.hp = self.max_hp = config.PLAYER_MAX_HP
        self.coyote = 0.0
        self.jump_buf = 0.0
        self.jump_cut_armed = False
        self.attack_t = -1.0
        self.pogo = False
        self.hit_set = set()
        self.inv = 0.0
        self.stun = 0.0
        self.anim = 0.0

    @property
    def attacking(self):
        return self.attack_t >= 0.0

    def start_attack(self, pogo=False):
        """Begin a swing; a requested pogo becomes downward when airborne."""
        if self.stun > 0.0 or self.attacking:
            return False
        self.attack_t = 0.0
        self.pogo = bool(pogo and not self.on_ground)
        self.hit_set = set()
        return True

    def pogo_bounce(self):
        """Bounce upward from a downward hit without granting i-frames."""
        self.vy = -config.POGO_BOUNCE_SPEED
        self.jump_cut_armed = False
        self.on_ground = False

    def update(self, dt, level, move_axis, jump_held):
        self.inv -= dt
        self.stun -= dt
        self.anim += dt

        if self.stun <= 0.0:
            if move_axis and not self.attacking:
                self.facing = move_axis
            air_attack = self.attacking and not self.on_ground
            # An air attack keeps its momentum. With a direction held it can
            # still steer at full speed; without one, velocity is preserved.
            if not (air_attack and not move_axis):
                speed = config.RUN_SPEED
                if self.attacking and not air_attack:
                    speed *= config.ATTACK_MOVE_MULT
                target_vx = move_axis * speed
                accel = config.ACCEL_RUN if move_axis else config.DECEL_RUN
                self.vx = approach(self.vx, target_vx, accel * dt)
        else:
            self.vx = approach(self.vx, 0.0, config.DECEL_STUN * dt)

        self.coyote = config.COYOTE_TIME if self.on_ground else self.coyote - dt
        self.jump_buf -= dt
        if self.jump_buf > 0.0 and self.coyote > 0.0 and self.stun <= 0.0:
            self.vy = -config.JUMP_SPEED
            self.jump_buf = 0.0
            self.coyote = 0.0
            self.jump_cut_armed = True

        # Variable jump height: check the current held state in the fixed step.
        if self.jump_cut_armed and not jump_held and self.vy < config.JUMP_CUT_SPEED:
            self.vy *= config.JUMP_CUT_MULT
            self.jump_cut_armed = False

        self.vy = min(self.vy + config.GRAVITY * dt, config.MAX_FALL)
        self.move(dt, level)

        if self.on_ground:
            self.jump_cut_armed = False
        elif self.vy >= 0.0:
            self.jump_cut_armed = False

        if self.attacking:
            self.attack_t += dt
            if self.attack_t >= config.ATTACK_TOTAL:
                self.attack_t = -1.0
                self.pogo = False

    def sprite(self):
        if self.attacking:
            frame = sprites.PLAYER_ATTACK
        elif not self.on_ground:
            frame = sprites.PLAYER_AIR
        elif abs(self.vx) > 2.0:
            frame = sprites.PLAYER_RUN[int(self.anim * 10) % 2]
        else:
            frame = sprites.PLAYER_IDLE
        return frame if self.facing > 0 else sprites.mirror(frame)


class EnemyState(enum.Enum):
    IDLE = "idle"
    PATROL = "patrol"
    FLOAT = "float"
    WINDUP = "windup"
    ATTACK = "attack"
    DIVE = "dive"
    RECOVER = "recover"


class Enemy(Body):
    """Shared health, hit reaction, state timer and death FX for enemies."""

    def __init__(self, x, y, kind, rng):
        data = config.ENEMY_DATA[kind]
        super().__init__(x, y, data["w"], data["h"])
        self.kind = kind
        self.data = data
        self.rng = rng
        self.hp = self.max_hp = data["hp"]
        self.stun = 0.0
        self.flash = 0.0
        self.anim = rng.random()
        self.state = None
        self.state_time = 0.0
        self.state_duration = None

    def set_state(self, state, duration=None):
        self.state = state
        self.state_time = 0.0
        self.state_duration = duration

    @property
    def timed_out(self):
        return (self.state_duration is not None
                and self.state_time + config.EPS >= self.state_duration)

    def update_timers(self, dt):
        self.stun -= dt
        self.flash -= dt
        self.anim += dt
        self.state_time += dt

    @property
    def contact_damage_enabled(self):
        return (self.state is not None
                and self.state.value in self.data["contact_states"])

    @property
    def color(self):
        return self.data["color"]

    @property
    def telegraph(self):
        return False

    def take_hit(self, direction):
        """Apply knockback, stun and flash, then return True if this kills."""
        self.hp -= 1
        self.vx = direction * self.data["knockback_x"]
        self.vy = self.data["knockback_y"]
        self.stun = self.data["stun_time"]
        self.flash = self.data["flash_time"]
        return self.hp <= 0

    def hit_burst(self, particles):
        particles.burst(self.x + self.w / 2.0, self.y + self.h / 2.0, 8,
                        config.HIT_PARTICLE_COLORS)

    def death_burst(self, particles):
        particles.burst(self.x + self.w / 2.0, self.y + self.h / 2.0, 25,
                        config.DEATH_PARTICLE_COLORS, speed=20.0)

    def update(self, dt, level, player, projectiles=None):
        raise NotImplementedError


class Crawler(Enemy):
    """Ground patroller that turns at walls and ledges."""

    def __init__(self, x, y, rng):
        super().__init__(x, y, "crawler", rng)
        self.dir = rng.choice((-1, 1))
        self.set_state(EnemyState.PATROL)

    def update(self, dt, level, player, projectiles=None):
        self.update_timers(dt)

        if self.stun > 0.0:
            self.vx = approach(self.vx, 0.0, self.data["stun_decel"] * dt)
        else:
            self.vx = self.dir * self.data["speed"]

        self.vy = min(self.vy + config.GRAVITY * dt, config.MAX_FALL)
        hit_wall = self.move(dt, level)

        if self.stun <= 0.0 and self.state is EnemyState.PATROL:
            if self.dir > 0:
                front = int(self.x + self.w + 0.3)
            else:
                front = int(self.x - 0.3)
            ledge = self.on_ground and not level.solid_at(front, int(self.y + self.h + 0.1))
            if hit_wall or ledge:
                self.dir = -self.dir

    def sprite(self):
        return sprites.CRAWLER_FRAMES[int(self.anim * self.data["anim_fps"]) % 2]


class Flyer(Enemy):
    """Hovering enemy: FLOAT -> WINDUP -> DIVE -> RECOVER -> FLOAT.

    Gravity never applies. Every move goes through Body.move, so the flyer
    still collides with the level while hovering, diving and retreating.
    """

    def __init__(self, x, y, rng):
        super().__init__(x, y, "flyer", rng)
        self.home_x = self.x + self.w / 2.0
        self.home_y = self.y + self.h / 2.0
        self.float_time = 0.0
        self.cooldown = 0.0
        self.target_x = self.home_x
        self.target_y = self.home_y
        self.dive_dx = 0.0
        self.dive_dy = 1.0
        self.facing = 1
        self.set_state(EnemyState.FLOAT)

    @property
    def color(self):
        if self.state is EnemyState.WINDUP:
            return self.data["windup_color"]
        if self.state is EnemyState.DIVE:
            return self.data["attack_color"]
        return super().color

    @property
    def telegraph(self):
        return self.state is EnemyState.WINDUP

    @staticmethod
    def _player_center(player):
        return player.x + player.w / 2.0, player.y + player.h / 2.0

    def _seek(self, target_x, target_y, speed, dt, level):
        """Move toward a world point at a capped speed, with tile collision."""
        cx = self.x + self.w / 2.0
        cy = self.y + self.h / 2.0
        dx = target_x - cx
        dy = target_y - cy
        dist = math.hypot(dx, dy)
        if dist <= 1e-6:
            self.vx = self.vy = 0.0
        else:
            step = min(speed * dt, dist)
            self.vx = dx / dist * (step / dt)
            self.vy = dy / dist * (step / dt)
        self.move(dt, level)

    def _enter_windup(self, player):
        self.target_x, self.target_y = self._player_center(player)
        self.vx = self.vy = 0.0
        self.set_state(EnemyState.WINDUP, self.data["windup_time"])

    def _start_dive(self):
        cx = self.x + self.w / 2.0
        cy = self.y + self.h / 2.0
        dx = self.target_x - cx
        dy = self.target_y - cy
        dist = math.hypot(dx, dy)
        if dist <= 1e-6:
            self.dive_dx, self.dive_dy = 0.0, 1.0
        else:
            self.dive_dx, self.dive_dy = dx / dist, dy / dist
        self.set_state(EnemyState.DIVE, self.data["attack_time"])

    def _update_float(self, dt, level, player):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.float_time += dt
        target_x = (self.home_x
                    + math.sin(self.float_time * self.data["float_freq_x"])
                    * self.data["float_amp_x"])
        target_y = (self.home_y
                    + math.sin(self.float_time * self.data["float_freq_y"])
                    * self.data["float_amp_y"])
        self._seek(target_x, target_y, self.data["speed"], dt, level)

        px, py = self._player_center(player)
        dx = abs(px - (self.x + self.w / 2.0))
        dy = abs(py - (self.y + self.h / 2.0))
        if (self.cooldown <= 0.0
                and dx <= self.data["aggro_x"]
                and dy <= self.data["aggro_y"]):
            self._enter_windup(player)

    def update(self, dt, level, player, projectiles=None):
        self.update_timers(dt)
        px, _ = self._player_center(player)
        self.facing = 1 if px >= self.x + self.w / 2.0 else -1

        if self.stun > 0.0:
            self.vx = approach(self.vx, 0.0, self.data["stun_decel"] * dt)
            self.vy = approach(self.vy, 0.0, self.data["stun_decel"] * dt)
            self.move(dt, level)
            return

        if self.state is EnemyState.FLOAT:
            self._update_float(dt, level, player)

        elif self.state is EnemyState.WINDUP:
            self.vx = self.vy = 0.0
            if self.timed_out:
                self._start_dive()

        elif self.state is EnemyState.DIVE:
            self.vx = self.dive_dx * self.data["dive_speed"]
            self.vy = self.dive_dy * self.data["dive_speed"]
            hit_wall = self.move(dt, level)
            if hit_wall or self.on_ground or self.timed_out:
                self.set_state(EnemyState.RECOVER, self.data["recover_time"])

        elif self.state is EnemyState.RECOVER:
            self._seek(self.home_x, self.home_y, self.data["speed"], dt, level)
            if self.timed_out:
                self.cooldown = self.data["cooldown"]
                self.float_time = 0.0
                self.set_state(EnemyState.FLOAT)

    def sprite(self):
        frame = sprites.FLYER_FRAMES[int(self.anim * self.data["anim_fps"]) % 2]
        return frame if self.facing > 0 else sprites.mirror(frame)


class Spitter(Enemy):
    """Ground enemy that keeps its preferred range and fires projectiles.

    IDLE repositions and waits out its cooldown; WINDUP is a half-second
    colour-coded telegraph; ATTACK spawns exactly one shot; RECOVER delays
    the next attempt.
    """

    def __init__(self, x, y, rng):
        super().__init__(x, y, "spitter", rng)
        self.facing = -1
        self.cooldown = self.data["cooldown"]
        self.set_state(EnemyState.IDLE)

    @property
    def color(self):
        if self.state is EnemyState.WINDUP:
            return self.data["windup_color"]
        if self.state is EnemyState.ATTACK:
            return self.data["attack_color"]
        return super().color

    @property
    def telegraph(self):
        return self.state is EnemyState.WINDUP

    def _player_center(self, player):
        return player.x + player.w / 2.0, player.y + player.h / 2.0

    def _ledge_ahead(self, level, direction):
        if not self.on_ground:
            return False
        if direction > 0:
            front = int(self.x + self.w + 0.3)
        else:
            front = int(self.x - 0.3)
        return not level.solid_at(front, int(self.y + self.h + 0.1))

    def _fall_and_move(self, dt, level):
        self.vy = min(self.vy + config.GRAVITY * dt, config.MAX_FALL)
        return self.move(dt, level)

    def _ground_step(self, dt, level, move_dir=0.0):
        self.vx = move_dir * self.data["speed"] if move_dir else 0.0
        return self._fall_and_move(dt, level)

    def _spawn_projectile(self, projectiles, player):
        if projectiles is None:
            return
        px, _ = self._player_center(player)
        direction = 1 if px >= self.x + self.w / 2.0 else -1
        self.facing = direction
        sx = self.x + (self.w if direction > 0 else -1.0)
        sy = self.y + self.h / 2.0 - 0.5
        projectiles.spawn(
            sx, sy,
            direction * self.data["projectile_speed"], 0.0,
            damage=self.data["projectile_damage"],
            color=self.data["projectile_color"],
            char=self.data["projectile_char"],
        )

    def _update_idle(self, dt, level, player):
        self.cooldown = max(0.0, self.cooldown - dt)
        px, py = self._player_center(player)
        dx = px - (self.x + self.w / 2.0)
        self.facing = 1 if dx >= 0.0 else -1
        dist = abs(dx)

        move_dir = 0.0
        if dist <= self.data["aggro_x"]:
            if dist > self.data["preferred_range"] + self.data["range_tolerance"]:
                move_dir = self.facing
            elif dist < self.data["preferred_range"] - self.data["range_tolerance"]:
                move_dir = -self.facing
        if move_dir and self._ledge_ahead(level, move_dir):
            move_dir = 0.0
        self._ground_step(dt, level, move_dir)

        dy = abs(py - (self.y + self.h / 2.0))
        if (self.cooldown <= 0.0
                and dist <= self.data["aggro_x"]
                and dy <= self.data["aggro_y"]):
            self.vx = 0.0
            self.set_state(EnemyState.WINDUP, self.data["windup_time"])

    def update(self, dt, level, player, projectiles=None):
        self.update_timers(dt)

        if self.stun > 0.0:
            self.vx = approach(self.vx, 0.0, self.data["stun_decel"] * dt)
            self._fall_and_move(dt, level)
            return

        if self.state is EnemyState.IDLE:
            self._update_idle(dt, level, player)

        elif self.state is EnemyState.WINDUP:
            self._ground_step(dt, level)
            if self.timed_out:
                self.set_state(EnemyState.ATTACK, self.data["attack_time"])
                self._spawn_projectile(projectiles, player)

        elif self.state is EnemyState.ATTACK:
            self._ground_step(dt, level)
            if self.timed_out:
                self.set_state(EnemyState.RECOVER, self.data["recover_time"])

        elif self.state is EnemyState.RECOVER:
            self._ground_step(dt, level)
            if self.timed_out:
                self.cooldown = self.data["cooldown"]
                self.set_state(EnemyState.IDLE)

    def sprite(self):
        frame = sprites.SPITTER_FRAMES[int(self.anim * self.data["anim_fps"]) % 2]
        return frame if self.facing > 0 else sprites.mirror(frame)


ENEMY_CLASSES = {
    "crawler": Crawler,
    "flyer": Flyer,
    "spitter": Spitter,
}


def create_enemy(kind, x, y, rng):
    """Construct the correct enemy class for a level spawn marker."""
    if kind == "boss":
        # Lazy import avoids a cycle: boss.py imports Enemy from this module.
        from .boss import Boss
        return Boss(x, y, rng)
    try:
        cls = ENEMY_CLASSES[kind]
    except KeyError:
        raise ValueError(f"unknown enemy type: {kind!r}") from None
    return cls(x, y, rng)
