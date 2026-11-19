"""Level data, the demo level builder, and the camera."""
from . import config


class Level:
    """A rectangular tile grid plus spawn metadata.

    Tile meaning: '#'/'=' solid, '"' decorative grass, '.'/' ' empty.
    Rooms loaded from ``assets/rooms/*.txt`` subclass this with door data.
    """

    def __init__(self, tiles, enemy_spawns, player_spawn):
        self.tiles = tiles
        self.height = len(tiles)
        self.width = len(tiles[0]) if tiles else 0
        self.enemy_spawns = list(enemy_spawns)
        self.player_spawn = player_spawn

    def tile_at(self, tx, ty):
        if 0 <= tx < self.width and 0 <= ty < self.height:
            return self.tiles[ty][tx]
        return " "

    def solid_at(self, tx, ty):
        # The starter treats horizontal out-of-bounds and below-ground as solid.
        if tx < 0 or tx >= self.width or ty >= self.height:
            return True
        if ty < 0:
            return False
        return self.tiles[ty][tx] in "#="


def build_demo_level(rng):
    """Build the starter's single-room level with a caller-owned RNG."""
    width = config.DEMO_LEVEL_WIDTH
    height = config.DEMO_LEVEL_HEIGHT
    g = [[" "] * width for _ in range(height)]

    for y in range(25, 28):
        for x in range(width):
            g[y][x] = "#"
    for y in range(height):
        g[y][0] = g[y][width - 1] = "#"

    def platform(x, y, w):
        for i in range(w):
            g[y][x + i] = "="
            if rng.random() < 0.5:
                g[y - 1][x + i] = '"'

    for x, y, w in (
        (20, 21, 10),
        (36, 17, 8),
        (50, 21, 12),
        (70, 18, 10),
        (90, 21, 8),
        (104, 16, 12),
        (120, 20, 10),
    ):
        platform(x, y, w)

    for y in range(22, 25):
        g[y][62] = g[y][63] = "#"

    for x in range(2, width - 2):
        if g[24][x] == " " and rng.random() < 0.6:
            g[24][x] = '"'

    # Early crawlers teach ground combat; flyers are placed over the
    # platforms so their windup and dive are easy to read. The spitter holds
    # range on the open ground past the central wall.
    enemy_spawns = (
        ("crawler", 30, 10),
        ("flyer", 45, 14),
        ("crawler", 58, 10),
        ("flyer", 75, 14),
        ("spitter", 100, 10),
        ("flyer", 110, 12),
        ("crawler", 135, 10),
    )
    return Level(g, enemy_spawns, player_spawn=(4.0, 20.0))


class Camera:
    """Smooth horizontal follow camera, clamped to the level."""

    def __init__(self, view_width, level_width):
        self.view_width = view_width
        self.level_width = level_width
        self.x = 0.0

    def update(self, target_x, dt):
        max_x = max(0.0, self.level_width - self.view_width)
        target = max(0.0, min(max_x, target_x))
        self.x += (target - self.x) * min(1.0, config.CAMERA_SMOOTH * dt)

    @property
    def offset(self):
        return int(round(self.x))
