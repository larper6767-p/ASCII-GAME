"""All tunable numbers live here. Units are cells and seconds."""

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
COLS = 100                     # visible physics cells across
ROWS = 28                      # visible physics cells down

# Renderer v2 decouples physics cells from the character grid. One physics
# cell is drawn as GLYPH_SCALE x GLYPH_SCALE small glyph cells. None of the
# physics constants below are expressed in glyph cells.
GLYPH_SCALE = 2                # 2x2 glyph cells per physics tile
# Cell preset: "6x10" (default, fast) or "8x14" (larger glyphs, larger
# window). Use set_cell_mode() before creating a Renderer to switch.
CELL_MODE = "6x10"
CELL_PRESETS = {
    "6x10": (6, 10, 8),        # (cell_w, cell_h, font_size)
    "8x14": (8, 14, 12),
}
GLYPH_CELL_W, GLYPH_CELL_H, GLYPH_FONT_SIZE = CELL_PRESETS[CELL_MODE]
GLYPH_FONT_PATH = "assets/fonts/DejaVuSansMono.ttf"
GLYPH_FONT_BOLD = False


def set_cell_mode(mode):
    """Switch the glyph-cell preset; returns the new (w, h, font) triple."""
    global GLYPH_CELL_W, GLYPH_CELL_H, GLYPH_FONT_SIZE, CELL_MODE
    if mode not in CELL_PRESETS:
        raise KeyError(f"unknown cell mode {mode!r}")
    CELL_MODE = mode
    GLYPH_CELL_W, GLYPH_CELL_H, GLYPH_FONT_SIZE = CELL_PRESETS[mode]
    return CELL_PRESETS[mode]

RENDER_FPS = 60                # render cap; physics is independent of this
FIXED_DT = 1.0 / 60.0          # physics step
MAX_FRAME_DT = 0.25            # ignore huge stalls (seconds)
MAX_STEPS_PER_FRAME = 15       # spiral-of-death guard

# Renderer v2 effects. These are visual-only and never feed physics.
LIGHT_AMBIENT = 0.50           # base light level (0..1)
LIGHT_PLAYER_RADIUS = 9.0      # physics cells
LIGHT_PLAYER_STRENGTH = 0.95
LIGHT_PROJECTILE_RADIUS = 4.0
LIGHT_PROJECTILE_STRENGTH = 0.70
PARALLAX_FACTORS = (0.12, 0.30, 0.55)
BLOOM_SCALE = 8                # glow buffer is 1/8 screen resolution
BLOOM_BLUR_PASSES = 2
RENDER_PROFILE = False         # collect per-step timings when True

# Quality toggles (visual only). Bloom and parallax take effect immediately;
# the fog bank is baked into the parallax layers when Parallax is built, so
# QUALITY_FOG is read at startup for the baked bank and per frame for the
# drifting strips.
QUALITY_BLOOM = True
QUALITY_PARALLAX = True
QUALITY_FOG = True

# Entity readability. Sprites never dim below this light level, and every
# entity gets a soft glow so it separates from the background.
SPRITE_MIN_LIGHT = 0.45        # 0..1 floor for sprite lighting
ENTITY_GLOW_RADIUS = 2.6       # multiples of the glyph cell width
ENTITY_GLOW_STRENGTH = 0.42

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

# ---------------------------------------------------------------------------
# Room atmosphere (M6) - purely visual, set from room metadata
# ---------------------------------------------------------------------------
# Neutral defaults for levels without atmosphere metadata (the demo level).
# ATMO_SKY matches BG, so the sky is unchanged; the subtle rock tint keeps
# the default palette in the same cool family as the original renderer.
ATMO_SKY = BG
ATMO_ROCK = (170, 166, 196)
ATMO_ACCENT = (255, 176, 96)
ATMO_FOG = 1.0
ATMO_EMBER = (255, 138, 74)


def default_atmosphere():
    """Return a fresh default atmosphere dict for a room or renderer."""
    return {
        "name": "default",
        "sky": ATMO_SKY,
        "rock": ATMO_ROCK,
        "accent": ATMO_ACCENT,
        "fog": ATMO_FOG,
        "ember": ATMO_EMBER,
    }


# Flickering torch/fire tiles ('T' in room files) and ambient ember motes.
TORCH_LIGHT_RADIUS = 3.2       # physics cells
TORCH_LIGHT_STRENGTH = 1.0
TORCH_FLICKER_SPEED = 8.0
AMBIENT_EMBER_COUNT = 20
AMBIENT_EMBER_RISE = 0.045     # screen heights per second

# Sealed-room fail-safe. An out-of-bounds or completely inactive enemy is
# returned to its spawn once; a repeat escape, inactivity timeout or being
# embedded in geometry for LOCK_STUCK_SECONDS removes it, so a locked arena
# can never soft-lock on an unreachable enemy.
LOCK_STUCK_SECONDS = 3.0
LOCK_IDLE_SECONDS = 20.0
LOCK_ESCAPE_RETURNS = 1

# HUD: bigger font, brighter colours and a dark panel for contrast.
HUD_FONT_SIZE = 16
HUD_PANEL_COLOR = (16, 18, 30, 215)
HUD_HEALTH_COLOR = (255, 96, 96)
HUD_HELP_COLOR = (205, 210, 235)
HUD_CLEAR_COLOR = (255, 226, 130)
HUD_TEXT_OUTLINE = (0, 0, 0)
HUD_OVERLAY_COLOR = (170, 235, 170)
HUD_INPUT_COLOR = (130, 220, 255)

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

# ---------------------------------------------------------------------------
# Boss (M7) - all boss tuning lives in this dict; enemy.py aliases it into
# ENEMY_DATA so room validation and generic spawn code can see the type.
# ---------------------------------------------------------------------------
BOSS_DATA = {
    "name": "Ember Warden",
    "w": 9,
    "h": 4,
    "hp": 18,
    "contact_damage": 2,
    # Only the charge body is a contact hazard; the attacks use projectiles.
    "contact_states": ("charge",),
    "knockback_x": 0.0,
    "knockback_y": 0.0,
    "stun_time": 0.0,
    "flash_time": 0.10,
    "stun_decel": 0.0,
    "anim_fps": 4.0,
    "color": (190, 72, 60),
    "windup_color": (255, 225, 90),
    "attack_color": (255, 110, 60),
    "phase_color": (255, 174, 82),
    "phase_two_color": (255, 92, 52),
    "intro_color": (220, 210, 255),
    "intro_time": 1.80,
    "idle_time": 1.10,
    "min_recovery": 0.75,
    "walk_speed": 3.5,
    "slam_windup": 0.85,
    "slam_active": 0.18,
    "slam_recover": 0.90,
    "slam_wave_speed": 18.0,
    "slam_wave_lifetime": 3.0,
    "slam_wave_damage": 1,
    "slam_wave_w": 3,
    "slam_wave_h": 2,
    "charge_windup": 0.75,
    "charge_speed": 30.0,
    "charge_time": 1.10,
    "charge_recover": 0.90,
    "rain_windup": 1.10,
    "rain_active": 1.40,
    "rain_recover": 0.90,
    "rain_count": 5,
    "rain_interval": 0.16,
    "rain_spread": 7.0,
    "rain_speed": 26.0,
    "rain_damage": 1,
    "phase_time": 1.30,
    "phase_threshold": 0.5,
    "phase_combo": ("slam", "rain"),
    "attack_choices": ("slam", "charge", "rain"),
    "warning_color": (255, 104, 70),
}

# The generic room loader, renderer and spawner index enemy stats by kind.
ENEMY_DATA["boss"] = BOSS_DATA
