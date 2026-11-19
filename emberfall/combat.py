"""Combat rules: hitbox shape, damage, knockback and hit-stop timing."""
from . import config


def attack_hitbox(player):
    """Return the sword AABB in world cells, or None when inactive.

    Bow and gun forms deal damage through friendly projectiles instead, so
    they intentionally expose no melee hitbox.
    """
    if getattr(player, "weapon", "sword") != "sword":
        return None
    if not (config.ATTACK_STARTUP <= player.attack_t < config.ATTACK_ACTIVE_END):
        return None
    if player.pogo:
        return (player.x, player.y + player.h, player.w, config.ATTACK_REACH)
    if player.facing > 0:
        bx = player.x + player.w
    else:
        bx = player.x - config.ATTACK_REACH
    return (bx, player.y, config.ATTACK_REACH, config.ATTACK_HEIGHT)


def damage_enemy(enemy, direction, damage=1):
    """Apply a hit. Caller handles FX and death removal."""
    enemy.take_hit(direction, damage)


def damage_player(player, source_x, damage=1):
    """Apply a contact hit and launch the player away from the source."""
    player.hp -= damage
    player.inv = config.PLAYER_IFRAMES
    player.stun = config.PLAYER_STUN_TIME
    direction = 1 if player.x > source_x else -1
    player.vx = direction * config.PLAYER_KNOCKBACK_X
    player.vy = config.PLAYER_KNOCKBACK_Y


class HitStop:
    """Freezes simulation for a short time after a hit lands."""

    def __init__(self):
        self.time = 0.0

    @property
    def active(self):
        return self.time > 0.0

    def trigger(self, seconds):
        # Deliberately overwrite (not extend), matching the starter's feel.
        self.time = seconds

    def update(self, dt):
        self.time = max(0.0, self.time - dt)
