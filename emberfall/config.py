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

# ---------------------------------------------------------------------------
# Enemies
# ---------------------------------------------------------------------------
CRAWLER_W = 3
CRAWLER_H = 2
CRAWLER_HP = 3
CRAWLER_SPEED = 6.0
CRAWLER_ANIM_FPS = 6.0
ENEMY_KNOCKBACK_X = 18.0
ENEMY_KNOCKBACK_Y = -10.0
ENEMY_STUN_TIME = 0.30
ENEMY_FLASH_TIME = 0.12
ENEMY_DECEL_STUN = 30.0

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
