"""M7 boss: the Ember Warden.

The boss is a heavy, ground-based enemy with three telegraphed attacks:

* ground slam - a windup, then two floor shockwaves travelling outwards;
* locked-direction charge - the aim is fixed when the windup starts;
* ember rain - floor warning marks, then seeded ember projectiles fall.

At half health the Warden visibly ignites (phase two) and chains a slam into
ember rain. Every attack ends in a recovery state whose duration is at least
``BOSS_DATA["min_recovery"]``. The intro is invulnerable.

All randomness comes from the seeded RNG handed to the enemy on construction;
there is no module-level ``random`` use.
"""
import enum

from . import config
from .entities import Enemy


class BossState(enum.Enum):
    INTRO = "intro"
    IDLE = "idle"
    SLAM_WINDUP = "slam_windup"
    SLAM_ACTIVE = "slam_active"
    SLAM_RECOVER = "slam_recover"
    CHARGE_WINDUP = "charge_windup"
    CHARGE = "charge"
    CHARGE_RECOVER = "charge_recover"
    RAIN_WINDUP = "rain_windup"
    RAIN_ACTIVE = "rain_active"
    RAIN_RECOVER = "rain_recover"
    PHASE_CHANGE = "phase_change"
    DEFEATED = "defeated"


WINDUP_STATES = (
    BossState.SLAM_WINDUP,
    BossState.CHARGE_WINDUP,
    BossState.RAIN_WINDUP,
)
ACTIVE_STATES = (
    BossState.SLAM_ACTIVE,
    BossState.CHARGE,
    BossState.RAIN_ACTIVE,
)


class Boss(Enemy):
    """The Ember Warden. ``kind`` stays "boss" for data lookups."""

    is_boss = True
    boss_name = "Ember Warden"

    def __init__(self, x, y, rng):
        super().__init__(x, y, "boss", rng)
        data = self.data
        self.name = data["name"]
        self.phase_two = False
        self.charge_dir = -1
        self.combo_queue = []
        self.warnings = []
        self.events = []
        self._rain_elapsed = 0.0
        self.facing = -1
        self.set_state(BossState.INTRO, data["intro_time"])

    # ------------------------------------------------------------------
    # Damage / visualization
    # ------------------------------------------------------------------
    @property
    def invulnerable(self):
        return self.state is BossState.INTRO

    @property
    def telegraph(self):
        return self.state in WINDUP_STATES + (BossState.PHASE_CHANGE,)

    @property
    def color(self):
        if self.state is BossState.INTRO:
            return self.data["intro_color"]
        if self.phase_two:
            if self.state is BossState.PHASE_CHANGE:
                return self.data["phase_color"]
            if self.state in WINDUP_STATES:
                return self.data["windup_color"]
            if self.state in ACTIVE_STATES:
                return self.data["phase_color"]
            return self.data["phase_two_color"]
        if self.state in WINDUP_STATES:
            return self.data["windup_color"]
        if self.state in ACTIVE_STATES:
            return self.data["attack_color"]
        return self.data["color"]

    def take_hit(self, direction, damage=1):
        """Bosses do not get knocked back or stunned.

        The intro is invulnerable. Crossing half HP starts the visible phase
        change; the killing hit wins over the phase transition.
        """
        if self.invulnerable:
            return False
        if self.hp <= 0:
            return True
        self.hp -= damage
        self.flash = self.data["flash_time"]
        if (self.hp > 0 and not self.phase_two
                and self.hp <= self.max_hp * self.data["phase_threshold"]):
            self._begin_phase_change()
        if self.hp <= 0:
            self.set_state(BossState.DEFEATED)
        return self.hp <= 0

    # ------------------------------------------------------------------
    # Events / geometry helpers
    # ------------------------------------------------------------------
    def _emit(self, event_type, **payload):
        event = {"type": event_type}
        event.update(payload)
        self.events.append(event)

    def consume_events(self):
        events = self.events
        self.events = []
        return events

    def _player_center(self, player):
        return player.x + player.w / 2.0, player.y + player.h / 2.0

    def _face_player(self, player):
        px, _ = self._player_center(player)
        if px != self.x + self.w / 2.0:
            self.facing = 1 if px > self.x + self.w / 2.0 else -1

    @staticmethod
    def _floor_below(level, x, y):
        """Return the y of the first solid tile top at or below ``y``."""
        tx = max(0, min(level.width - 1, int(x)))
        start = max(0, int(y))
        for ty in range(start, level.height):
            if level.solid_at(tx, ty):
                return float(ty)
        return float(level.height - 3)

    def _gravity_move(self, dt, level, vx=0.0):
        self.vx = vx
        self.vy = min(self.vy + config.GRAVITY * dt, config.MAX_FALL)
        return self.move(dt, level)

    # ------------------------------------------------------------------
    # Attack entry / transitions
    # ------------------------------------------------------------------
    def _begin_attack(self, attack, level, player):
        self.vx = 0.0
        self._face_player(player)
        if attack == "slam":
            self.set_state(BossState.SLAM_WINDUP, self.data["slam_windup"])
        elif attack == "charge":
            # The direction is locked now, before any player movement during
            # the windup. It is the only place the charge direction is set.
            self.charge_dir = (
                1 if self._player_center(player)[0] >= self.x + self.w / 2.0
                else -1
            )
            self.facing = self.charge_dir
            self.set_state(BossState.CHARGE_WINDUP,
                           self.data["charge_windup"])
        elif attack == "rain":
            self.set_state(BossState.RAIN_WINDUP, self.data["rain_windup"])
            self._make_warnings(level, player)
        else:
            raise ValueError(f"unknown boss attack {attack!r}")

    def _choose_attack(self):
        return self.rng.choice(self.data["attack_choices"])

    def _make_warnings(self, level, player):
        data = self.data
        px, _ = self._player_center(player)
        self.warnings = []
        for index in range(data["rain_count"]):
            if index == 0:
                wx = px
            else:
                wx = px + self.rng.uniform(
                    -data["rain_spread"], data["rain_spread"]
                )
            wx = max(1.0, min(level.width - 2.0, wx))
            floor_y = self._floor_below(
                level, wx, player.y + player.h + 0.1
            )
            self.warnings.append({
                "x": wx,
                "y": floor_y,
                "delay": index * data["rain_interval"],
                "fired": False,
            })
        self._rain_elapsed = 0.0

    def _spawn_shockwaves(self, projectiles):
        if projectiles is None:
            return
        data = self.data
        wave_y = self.y + self.h - data["slam_wave_h"]
        for direction, x in (
            (-1, self.x - data["slam_wave_w"]),
            (1, self.x + self.w),
        ):
            projectiles.spawn(
                x, wave_y,
                direction * data["slam_wave_speed"], 0.0,
                damage=data["slam_wave_damage"],
                color=data["attack_color"],
                char="~",
                w=data["slam_wave_w"],
                h=data["slam_wave_h"],
                lifetime=data["slam_wave_lifetime"],
                kind="shockwave",
            )
        self._emit(
            "slam",
            x=self.x + self.w / 2.0,
            y=self.y + self.h,
        )

    def _update_rain(self, dt, projectiles):
        self._rain_elapsed += dt
        data = self.data
        for warning in self.warnings:
            if warning["fired"] or self._rain_elapsed < warning["delay"]:
                continue
            warning["fired"] = True
            if projectiles is not None:
                projectiles.spawn(
                    warning["x"] - 0.5, 0.0,
                    0.0, data["rain_speed"],
                    damage=data["rain_damage"],
                    color=data["attack_color"],
                    char="v",
                    w=1,
                    h=1,
                    lifetime=6.0,
                    kind="ember",
                )

    def _enter_recovery(self, state, seconds):
        self.vx = 0.0
        self.set_state(state, max(self.data["min_recovery"], seconds))

    def _after_attack(self, level, player):
        if self.combo_queue:
            self._begin_attack(self.combo_queue.pop(0), level, player)
        else:
            idle = self.data["idle_time"] * (0.65 if self.phase_two else 1.0)
            self.set_state(BossState.IDLE, idle)

    def _begin_phase_change(self):
        self.phase_two = True
        self.combo_queue = list(self.data["phase_combo"])
        self.warnings.clear()
        self.vx = self.vy = 0.0
        self.set_state(BossState.PHASE_CHANGE, self.data["phase_time"])
        self._emit(
            "phase",
            x=self.x + self.w / 2.0,
            y=self.y + self.h / 2.0,
        )

    # ------------------------------------------------------------------
    # Main update
    # ------------------------------------------------------------------
    def update(self, dt, level, player, projectiles=None):
        self.update_timers(dt)
        if self.state is BossState.DEFEATED:
            return

        if self.stun > 0.0:
            self.vx = 0.0
            self._gravity_move(dt, level)
            return

        state = self.state
        data = self.data

        if state is BossState.INTRO:
            self._face_player(player)
            self._gravity_move(dt, level)
            if self.timed_out:
                self.set_state(BossState.IDLE, data["idle_time"])
                self._emit("intro_done", x=self.x, y=self.y)
            return

        if state is BossState.PHASE_CHANGE:
            self._face_player(player)
            self._gravity_move(dt, level)
            if self.timed_out:
                self._after_attack(level, player)
            return

        if state is BossState.IDLE:
            self._face_player(player)
            px, _ = self._player_center(player)
            distance = abs(px - (self.x + self.w / 2.0))
            walk = 0.0
            if distance > self.w / 2.0 + 6.0:
                walk = self.facing * data["walk_speed"]
            self._gravity_move(dt, level, walk)
            if self.timed_out:
                if self.combo_queue:
                    self._begin_attack(self.combo_queue.pop(0), level, player)
                else:
                    self._begin_attack(self._choose_attack(), level, player)
            return

        if state is BossState.SLAM_WINDUP:
            self._face_player(player)
            self._gravity_move(dt, level)
            if self.timed_out:
                self.set_state(BossState.SLAM_ACTIVE,
                               data["slam_active"])
                self._spawn_shockwaves(projectiles)
            return

        if state is BossState.SLAM_ACTIVE:
            self._gravity_move(dt, level)
            if self.timed_out:
                self._enter_recovery(BossState.SLAM_RECOVER,
                                     data["slam_recover"])
            return

        if state is BossState.SLAM_RECOVER:
            self._gravity_move(dt, level)
            if self.timed_out:
                self._after_attack(level, player)
            return

        if state is BossState.CHARGE_WINDUP:
            # Keep the locked facing: do not track the player here.
            self._gravity_move(dt, level)
            if self.timed_out:
                self.set_state(BossState.CHARGE, data["charge_time"])
                self.vx = self.charge_dir * data["charge_speed"]
                self._emit("charge_start", dir=self.charge_dir)
            return

        if state is BossState.CHARGE:
            hit_wall = self._gravity_move(
                dt, level, self.charge_dir * data["charge_speed"]
            )
            if hit_wall or self.timed_out:
                self._emit("charge_stop", dir=self.charge_dir)
                self._enter_recovery(BossState.CHARGE_RECOVER,
                                     data["charge_recover"])
            return

        if state is BossState.CHARGE_RECOVER:
            self._gravity_move(dt, level)
            if self.timed_out:
                self._after_attack(level, player)
            return

        if state is BossState.RAIN_WINDUP:
            self._face_player(player)
            self._gravity_move(dt, level)
            if self.timed_out:
                self.set_state(BossState.RAIN_ACTIVE,
                               data["rain_active"])
                self._rain_elapsed = 0.0
                self._emit("rain_start", count=len(self.warnings))
            return

        if state is BossState.RAIN_ACTIVE:
            self._gravity_move(dt, level)
            self._update_rain(dt, projectiles)
            if self.timed_out:
                self.warnings.clear()
                self._enter_recovery(BossState.RAIN_RECOVER,
                                     data["rain_recover"])
            return

        if state is BossState.RAIN_RECOVER:
            self._gravity_move(dt, level)
            if self.timed_out:
                self._after_attack(level, player)
