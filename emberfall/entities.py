"""Player and enemy entities. AI is a small explicit state machine per type."""
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
        self.hit_set = set()
        self.inv = 0.0
        self.stun = 0.0
        self.anim = 0.0

    @property
    def attacking(self):
        return self.attack_t >= 0.0

    def start_attack(self):
        """Begin a swing. Returns False while stunned or already swinging."""
        if self.stun > 0.0 or self.attacking:
            return False
        self.attack_t = 0.0
        self.hit_set = set()
        return True

    def update(self, dt, level, move_axis, jump_held):
        self.inv -= dt
        self.stun -= dt
        self.anim += dt

        if self.stun <= 0.0:
            if move_axis and not self.attacking:
                self.facing = move_axis
            speed = config.RUN_SPEED * (config.ATTACK_MOVE_MULT if self.attacking else 1.0)
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


class Enemy(Body):
    """Shared health/knockback state for enemy subclasses."""

    def __init__(self, x, y, w, h, hp):
        super().__init__(x, y, w, h)
        self.hp = hp
        self.stun = 0.0
        self.flash = 0.0
        self.anim = 0.0

    def update_timers(self, dt):
        self.stun -= dt
        self.flash -= dt
        self.anim += dt


class Crawler(Enemy):
    """Ground patroller that turns at walls and ledges."""

    def __init__(self, x, y, rng):
        super().__init__(x, y, config.CRAWLER_W, config.CRAWLER_H, config.CRAWLER_HP)
        self.dir = rng.choice((-1, 1))
        self.anim = rng.random()

    def update(self, dt, level):
        self.update_timers(dt)

        if self.stun <= 0.0:
            self.vx = self.dir * config.CRAWLER_SPEED
        else:
            self.vx = approach(self.vx, 0.0, config.ENEMY_DECEL_STUN * dt)

        self.vy = min(self.vy + config.GRAVITY * dt, config.MAX_FALL)
        hit_wall = self.move(dt, level)

        if self.stun <= 0.0:
            if self.dir > 0:
                front = int(self.x + self.w + 0.3)
            else:
                front = int(self.x - 0.3)
            ledge = self.on_ground and not level.solid_at(front, int(self.y + self.h + 0.1))
            if hit_wall or ledge:
                self.dir = -self.dir

    def sprite(self):
        return sprites.CRAWLER_FRAMES[int(self.anim * config.CRAWLER_ANIM_FPS) % 2]
