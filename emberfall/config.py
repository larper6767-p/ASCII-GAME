"""All tunable numbers live here. Units are cells and seconds."""

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
COLS = 100                     # visible grid width in characters
ROWS = 28                      # visible grid height in characters
FONT_SIZE = 16
# On Windows this list currently resolves to Courier New (11x19 cells).
# Put "consolas" first to compare a slightly narrower glyph.
FONT_NAME = "dejavusansmono,consolas,menlo,couriernew,monospace"
FONT_BOLD = True

RENDER_FPS = 60                # render cap; physics is independent of this
FIXED_DT = 1.0 / 60.0          # physics step
MAX_FRAME_DT = 0.25            # ignore huge stalls (seconds)
MAX_STEPS_PER_FRAME = 15       # spiral-of-death guard

# ---------------------------------------------------------------------------
# Physics (float cell units)
# ---------------------------------------------------------------------------
GRAVITY = 95.0                 # cells / s^2
MAX_FALL = 55.0                # cells / s
RUN_SPEED = 28.0               # cells / s
JUMP_SPEED = 31.0              # cells / s, about 5 rows
COYOTE_TIME = 0.10             # seconds you can still jump after leaving a ledge
JUMP_BUFFER_TIME = 0.10        # seconds an early jump press is remembered
JUMP_CUT_MULT = 0.45           # upward velocity retained when jump is released
JUMP_CUT_SPEED = -8.0          # only cut while rising faster than this
EPS = 1e-6

ACCEL_RUN = 220.0              # horizontal acceleration when steering
DECEL_RUN = 300.0              # horizontal deceleration when no input
DECEL_STUN = 40.0              # horizontal deceleration while stunned

# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------
PLAYER_W = 3
PLAYER_H = 3
PLAYER_MAX_HP = 5
PLAYER_IFRAMES = 1.0           # seconds of invulnerability after a hit
PLAYER_STUN_TIME = 0.25        # seconds of control loss after a hit
PLAYER_KNOCKBACK_X = 22.0
PLAYER_KNOCKBACK_Y = -16.0
ATTACK_MOVE_MULT = 0.3         # movement speed multiplier while attacking
ATTACK_STARTUP = 0.06          # seconds before the hitbox appears
ATTACK_ACTIVE_END = 0.18       # hitbox disappears here
ATTACK_TOTAL = 0.32            # full swing duration
ATTACK_REACH = 4               # cells in front of the player
ATTACK_HEIGHT = 3
POGO_BOUNCE_SPEED = 22.0       # upward velocity after a downward hit

# Enemy stats are data-driven in ENEMY_DATA at the bottom of this file.

# ---------------------------------------------------------------------------
# Projectiles
# ---------------------------------------------------------------------------
PROJECTILE_LIFETIME = 8.0      # safety cleanup for shots that miss

# ---------------------------------------------------------------------------
# Combat juice
# ---------------------------------------------------------------------------
SWORD_HITSTOP = 0.07
HURT_HITSTOP = 0.05
HIT_SHAKE = 0.15
HURT_SHAKE = 0.25
SHAKE_CELLS = 1

# ---------------------------------------------------------------------------
# World / camera
# ---------------------------------------------------------------------------
DEMO_LEVEL_WIDTH = 150
DEMO_LEVEL_HEIGHT = 28
CAMERA_SMOOTH = 8.0

# ---------------------------------------------------------------------------
# FX
# ---------------------------------------------------------------------------
PARTICLE_GRAVITY = 40.0
GRASS_WIND_SPEED = 1.8
GRASS_BEND_DISTANCE = 3.5

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BG = (12, 12, 18)
WHITE = (240, 240, 240)
PLAYER_COLOR = (120, 200, 255)
ENEMY_COLOR = (220, 70, 70)
HIT_PARTICLE_COLORS = (WHITE, (255, 220, 120))
DEATH_PARTICLE_COLORS = ((255, 90, 70), (255, 180, 80), WHITE)
PLAYER_HURT_PARTICLE_COLORS = ((255, 80, 80), WHITE)
HUD_HEALTH_COLOR = (255, 120, 120)
HUD_HELP_COLOR = (110, 110, 130)
HUD_CLEAR_COLOR = (255, 220, 120)

# ---------------------------------------------------------------------------
# Enemy types
# ---------------------------------------------------------------------------
# Every per-type value an enemy needs. Classes read this dict; add a new
# type here and map it to a class in entities.ENEMY_CLASSES.
ENEMY_DATA = {
    "crawler": {
        "w": 3,
        "h": 2,
        "hp": 3,
        "speed": 6.0,
        "contact_damage": 1,
        "contact_states": ("patrol",),
        "windup_time": 0.0,
        "attack_time": 0.0,
        "recover_time": 0.0,
        "knockback_x": 18.0,
        "knockback_y": -10.0,
        "stun_time": 0.30,
        "flash_time": 0.12,
        "stun_decel": 30.0,
        "anim_fps": 6.0,
        "color": ENEMY_COLOR,
    },
    "flyer": {
        "w": 5,
        "h": 2,
        "hp": 2,
        "speed": 10.0,
        "contact_damage": 1,
        "contact_states": ("dive",),
        "windup_time": 0.45,
        "attack_time": 0.55,
        "recover_time": 0.70,
        "cooldown": 1.30,
        "knockback_x": 20.0,
        "knockback_y": -8.0,
        "stun_time": 0.30,
        "flash_time": 0.12,
        "stun_decel": 28.0,
        "anim_fps": 8.0,
        "dive_speed": 32.0,
        "aggro_x": 24.0,
        "aggro_y": 14.0,
        "float_amp_x": 2.0,
        "float_amp_y": 1.2,
        "float_freq_x": 0.9,
        "float_freq_y": 2.0,
        "color": (195, 120, 230),
        "windup_color": (255, 225, 90),
        "attack_color": (255, 150, 80),
    },
    "spitter": {
        "w": 3,
        "h": 3,
        "hp": 3,
        "speed": 7.0,
        "contact_damage": 1,
        "contact_states": ("idle", "windup", "attack", "recover"),
        "windup_time": 0.50,
        "attack_time": 0.15,
        "recover_time": 0.40,
        "cooldown": 1.10,
        "knockback_x": 18.0,
        "knockback_y": -10.0,
        "stun_time": 0.30,
        "flash_time": 0.12,
        "stun_decel": 30.0,
        "anim_fps": 5.0,
        "preferred_range": 13.0,
        "range_tolerance": 3.0,
        "aggro_x": 28.0,
        "aggro_y": 16.0,
        "projectile_speed": 13.0,
        "projectile_damage": 1,
        "projectile_color": (150, 255, 150),
        "projectile_char": "*",
        "color": (115, 215, 125),
        "windup_color": (255, 225, 90),
        "attack_color": (255, 150, 80),
    },
}
