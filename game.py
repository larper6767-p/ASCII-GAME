"""
ASCII KNIGHT - a starter for a Hollow Knight-style side-scroller drawn entirely in characters.

Run:      pip install pygame   (then)   python ascii_knight.py
Controls: A/D or arrows = move | SPACE/W/Z = jump (release early for short hop)
          J/X = attack | R = restart | ESC = quit

How it works:
  * The world is a grid of characters. Physics runs in float "cell" units, and
    we round to the nearest cell only when drawing.
  * Characters are ~2x taller than wide, so horizontal speeds are bigger than
    vertical ones. Tweak the constants below to taste.
  * Everything is drawn through one function, put(), so adding CRT effects,
    colour palettes etc. later is easy.
"""
import math
import random
import sys

import pygame

# ----------------------------------------------------------------------------
# Tunables
# ----------------------------------------------------------------------------
COLS, ROWS = 100, 28          # visible grid size (in characters)
LW, LH = 150, 28              # level size (in characters)
FPS = 60
GRAVITY = 95.0                # cells / s^2
MAX_FALL = 55.0
RUN_SPEED = 28.0              # cells / s
JUMP_SPEED = 31.0
COYOTE = 0.10                 # seconds you can still jump after leaving a ledge
JUMP_BUFFER = 0.10            # seconds a early jump press is remembered
ATTACK_STARTUP, ATTACK_ACTIVE, ATTACK_TOTAL = 0.06, 0.18, 0.32
EPS = 1e-6

BG = (12, 12, 18)
WHITE = (240, 240, 240)

# ----------------------------------------------------------------------------
# Level  (built in code here; swap for a text file with parse_level() if you like)
# ----------------------------------------------------------------------------
grid = []
ENEMY_SPAWNS = []


def build_level():
    global grid, ENEMY_SPAWNS
    random.seed(7)
    g = [[" "] * LW for _ in range(LH)]
    for y in range(25, 28):
        for x in range(LW):
            g[y][x] = "#"
    for y in range(LH):
        g[y][0] = g[y][LW - 1] = "#"

    def plat(x, y, w):
        for i in range(w):
            g[y][x + i] = "="
            if random.random() < 0.5:
                g[y - 1][x + i] = '"'

    for x, y, w in [(20, 21, 10), (36, 17, 8), (50, 21, 12), (70, 18, 10),
                    (90, 21, 8), (104, 16, 12), (120, 20, 10)]:
        plat(x, y, w)
    for y in range(22, 25):                      # a small wall to hop over
        g[y][62] = g[y][63] = "#"
    for x in range(2, LW - 2):                   # grass on the ground
        if g[24][x] == " " and random.random() < 0.6:
            g[24][x] = '"'
    grid = g
    ENEMY_SPAWNS = [(30, 10), (45, 10), (58, 10), (75, 10), (96, 10), (110, 10), (135, 10)]


def parse_level(text):
    """Optional: load a level from text. '#','=' solid, '"' grass, '@' start, 'E' enemy."""
    global grid, ENEMY_SPAWNS
    rows = text.split("\n")
    width = max(len(r) for r in rows)
    grid = [list(r.ljust(width)) for r in rows]
    ENEMY_SPAWNS = []
    for y, row in enumerate(grid):
        for x, c in enumerate(row):
            if c == "E":
                ENEMY_SPAWNS.append((x, y))
                row[x] = " "


def solid_at(tx, ty):
    if tx < 0 or tx >= LW or ty >= LH:
        return True
    if ty < 0:
        return False
    return grid[ty][tx] in "#="


def collides(x, y, w, h):
    x0, x1 = math.floor(x), math.floor(x + w - EPS)
    y0, y1 = math.floor(y), math.floor(y + h - EPS)
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            if solid_at(tx, ty):
                return True
    return False


def overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def approach(v, target, step):
    if v < target:
        return min(v + step, target)
    return max(v - step, target)


# ----------------------------------------------------------------------------
# Sprites (right-facing; flipped automatically for left)
# ----------------------------------------------------------------------------
FLIP = str.maketrans("/\\()<>[]", "\\/)(><][")


def flip(lines):
    return [l[::-1].translate(FLIP) for l in lines]


P_IDLE = [" o ", "/|\\", "/ \\"]
P_RUN = [[" o ", "/|\\", "/ |"], [" o ", "/|\\", "| \\"]]
P_AIR = [" o ", "\\|/", "/ \\"]
P_ATTACK = [" o ", "/|>", "/ \\"]
SLASH = ["  \\ ", "   )", "  / "]
E_FRAMES = [["/^\\", "<_>"], ["/^\\", ">_<"]]


# ----------------------------------------------------------------------------
# Entities
# ----------------------------------------------------------------------------
class Body:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.vx = self.vy = 0.0
        self.on_ground = False

    @property
    def rect(self):
        return (self.x, self.y, self.w, self.h)

    def move(self, dt):
        """Move axis by axis and snap to tile edges. Returns True if we hit a wall."""
        hit_wall = False
        self.x += self.vx * dt
        if collides(*self.rect):
            if self.vx > 0:
                self.x = math.floor(self.x + self.w - EPS) - self.w
            else:
                self.x = math.floor(self.x) + 1
            self.vx = 0
            hit_wall = True
        self.y += self.vy * dt
        self.on_ground = False
        if collides(*self.rect):
            if self.vy > 0:
                self.y = math.floor(self.y + self.h - EPS) - self.h
                self.on_ground = True
            else:
                self.y = math.floor(self.y) + 1
            self.vy = 0
        return hit_wall


class Player(Body):
    def __init__(self):
        super().__init__(4, 20, 3, 3)
        self.facing = 1
        self.hp, self.max_hp = 5, 5
        self.coyote = self.jump_buf = 0.0
        self.attack_t = -1.0
        self.hit_set = set()
        self.inv = self.stun = 0.0
        self.anim = 0.0

    @property
    def attacking(self):
        return self.attack_t >= 0

    @property
    def hitbox(self):
        if ATTACK_STARTUP <= self.attack_t < ATTACK_ACTIVE:
            bx = self.x + self.w if self.facing > 0 else self.x - 4
            return (bx, self.y, 4, 3)
        return None

    def start_attack(self):
        if not self.attacking:
            self.attack_t = 0.0
            self.hit_set = set()

    def update(self, dt, keys):
        self.inv -= dt
        self.stun -= dt
        self.anim += dt
        direction = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        if self.stun <= 0:
            if direction and not self.attacking:
                self.facing = direction
            speed = RUN_SPEED * (0.3 if self.attacking else 1.0)
            self.vx = approach(self.vx, direction * speed, (220 if direction else 300) * dt)
        else:
            self.vx = approach(self.vx, 0, 40 * dt)

        self.coyote = COYOTE if self.on_ground else self.coyote - dt
        self.jump_buf -= dt
        if self.jump_buf > 0 and self.coyote > 0 and self.stun <= 0:
            self.vy = -JUMP_SPEED
            self.jump_buf = self.coyote = 0

        self.vy = min(self.vy + GRAVITY * dt, MAX_FALL)
        self.move(dt)

        if self.attacking:
            self.attack_t += dt
            if self.attack_t >= ATTACK_TOTAL:
                self.attack_t = -1.0

    def sprite(self):
        if self.attacking:
            s = P_ATTACK
        elif not self.on_ground:
            s = P_AIR
        elif abs(self.vx) > 2:
            s = P_RUN[int(self.anim * 10) % 2]
        else:
            s = P_IDLE
        return s if self.facing > 0 else flip(s)


class Enemy(Body):
    def __init__(self, x, y):
        super().__init__(x, y, 3, 2)
        self.hp = 3
        self.dir = random.choice((-1, 1))
        self.stun = self.flash = 0.0
        self.anim = random.random()

    def update(self, dt):
        self.stun -= dt
        self.flash -= dt
        self.anim += dt
        if self.stun <= 0:
            self.vx = self.dir * 6.0
        else:
            self.vx = approach(self.vx, 0, 30 * dt)
        self.vy = min(self.vy + GRAVITY * dt, MAX_FALL)
        hit = self.move(dt)
        if self.stun <= 0:
            front = math.floor(self.x + self.w + 0.3) if self.dir > 0 else math.floor(self.x - 0.3)
            ledge = self.on_ground and not solid_at(front, math.floor(self.y + self.h + 0.1))
            if hit or ledge:
                self.dir = -self.dir

    def sprite(self):
        return E_FRAMES[int(self.anim * 6) % 2]


# ----------------------------------------------------------------------------
# Game
# ----------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        self.font = pygame.font.SysFont("dejavusansmono,consolas,menlo,couriernew,monospace", 16, bold=True)
        self.cw = self.font.size("M")[0]
        self.ch = self.font.get_height()
        self.screen = pygame.display.set_mode((COLS * self.cw, ROWS * self.ch))
        pygame.display.set_caption("ASCII Knight")
        self.clock = pygame.time.Clock()
        self.glyphs = {}
        self.t = 0.0
        build_level()
        self.reset()

    def reset(self):
        self.player = Player()
        self.enemies = [Enemy(x, y) for x, y in ENEMY_SPAWNS]
        self.particles = []
        self.camx = 0.0
        self.hitstop = self.shake = 0.0

    # --- drawing helpers ---------------------------------------------------
    def put(self, sx, sy, c, color):
        if c == " " or not (0 <= sx < COLS and 0 <= sy < ROWS):
            return
        key = (c, color)
        g = self.glyphs.get(key)
        if g is None:
            g = self.glyphs[key] = self.font.render(c, True, color)
        self.screen.blit(g, (sx * self.cw, sy * self.ch))

    def put_text(self, sx, sy, text, color=WHITE):
        for i, c in enumerate(text):
            self.put(sx + i, sy, c, color)

    def world_sprite(self, lines, wx, wy, color, ox):
        bx, by = int(round(wx)) - ox, int(round(wy))
        for j, line in enumerate(lines):
            for i, c in enumerate(line):
                self.put(bx + i, by + j, c, color)

    # --- effects -----------------------------------------------------------
    def burst(self, x, y, n, colors, speed=14):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            s = random.uniform(0.3, 1.0) * speed
            self.particles.append([x, y, math.cos(a) * s * 1.6, math.sin(a) * s - 4,
                                   random.uniform(0.3, 0.7), random.choice("*'.,+x"), random.choice(colors)])

    def grass_char(self, wx, wy, p):
        wind = math.sin(self.t * 1.8 + wx * 0.35) * 0.7
        px, py = p.x + p.w / 2, p.y + p.h
        dx = wx - px
        if abs(dx) < 3.5 and abs(wy - py) < 4:          # bend away from the player
            wind += math.copysign(1.2 * (1 - abs(dx) / 3.5), dx)
        tall = (wx * 7 + wy) % 3 != 0
        if tall:
            c = "\\" if wind < -0.35 else "/" if wind > 0.35 else "|"
        else:
            c = "`" if wind < -0.35 else "'" if wind > 0.35 else ","
        shade = 120 + (wx * 37) % 80
        return c, (50, shade, 60)

    # --- update ------------------------------------------------------------
    def update(self, dt, keys):
        p = self.player
        self.shake = max(0.0, self.shake - dt)

        if self.hitstop > 0:                    # hit-stop: freeze the world for a few frames
            self.hitstop -= dt
            return
        self.t += dt

        p.update(dt, keys)
        for e in self.enemies:
            e.update(dt)

        # sword hits
        hb = p.hitbox
        if hb:
            for e in list(self.enemies):
                if id(e) not in p.hit_set and overlap(hb, e.rect):
                    p.hit_set.add(id(e))
                    e.hp -= 1
                    e.vx, e.vy = p.facing * 18, -10
                    e.stun, e.flash = 0.3, 0.12
                    self.hitstop, self.shake = 0.07, 0.15
                    self.burst(e.x + 1.5, e.y + 1, 8, [WHITE, (255, 220, 120)])
                    if e.hp <= 0:
                        self.burst(e.x + 1.5, e.y + 1, 25, [(255, 90, 70), (255, 180, 80), WHITE], 20)
                        self.enemies.remove(e)

        # enemy touches player
        if p.inv <= 0:
            for e in self.enemies:
                if overlap(p.rect, e.rect):
                    p.hp -= 1
                    p.inv, p.stun = 1.0, 0.25
                    p.vx = (1 if p.x > e.x else -1) * 22
                    p.vy = -16
                    self.hitstop, self.shake = 0.05, 0.25
                    self.burst(p.x + 1.5, p.y + 1.5, 14, [(255, 80, 80), WHITE])
                    break
        if p.hp <= 0:
            self.reset()
            return

        # particles
        for q in self.particles:
            q[4] -= dt
            q[3] += 40 * dt
            q[0] += q[2] * dt
            q[1] += q[3] * dt
        self.particles = [q for q in self.particles if q[4] > 0 and not solid_at(int(q[0]), int(q[1]))]

        # camera
        target = max(0, min(LW - COLS, p.x + p.w / 2 - COLS / 2))
        self.camx += (target - self.camx) * min(1.0, 8 * dt)

    # --- draw --------------------------------------------------------------
    def draw(self):
        self.screen.fill(BG)
        p = self.player
        ox = int(round(self.camx))
        if self.shake > 0:
            ox += random.choice((-1, 0, 1))

        # tiles + grass
        for sy in range(ROWS):
            for sx in range(COLS):
                wx = ox + sx
                if not (0 <= wx < LW):
                    continue
                t = grid[sy][wx]
                if t == "#":
                    v = 70 + ((wx * 7 + sy * 13) % 3) * 12
                    self.put(sx, sy, "#", (v, v, v + 10))
                elif t == "=":
                    self.put(sx, sy, "=", (170, 120, 70))
                elif t == '"':
                    c, col = self.grass_char(wx, sy, p)
                    self.put(sx, sy, c, col)

        # enemies
        for e in self.enemies:
            col = WHITE if e.flash > 0 else (220, 70, 70)
            self.world_sprite(e.sprite(), e.x, e.y, col, ox)

        # player (blink while invulnerable)
        if p.inv <= 0 or int(p.inv * 20) % 2 == 0:
            self.world_sprite(p.sprite(), p.x, p.y, (120, 200, 255), ox)
        if p.attacking and p.attack_t >= ATTACK_STARTUP:
            slash = SLASH if p.facing > 0 else flip(SLASH)
            bx = p.x + p.w if p.facing > 0 else p.x - 4
            fade = (255, 255, 200) if p.attack_t < ATTACK_ACTIVE else (130, 130, 110)
            self.world_sprite(slash, bx, p.y, fade, ox)

        # particles
        for q in self.particles:
            self.put(int(q[0]) - ox, int(q[1]), q[5], q[6])

        # HUD
        self.put_text(2, 1, "HP [" + "#" * p.hp + "-" * (p.max_hp - p.hp) + "]", (255, 120, 120))
        self.put_text(2, 2, "A/D move  SPACE jump  J attack  R restart", (110, 110, 130))
        if not self.enemies:
            self.put_text(COLS // 2 - 8, 6, "ALL ENEMIES SLAIN", (255, 220, 120))

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                    pygame.quit()
                    sys.exit()
                if ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP, pygame.K_z):
                        self.player.jump_buf = JUMP_BUFFER
                    elif ev.key in (pygame.K_j, pygame.K_x):
                        self.player.start_attack()
                    elif ev.key == pygame.K_r:
                        self.reset()
                if ev.type == pygame.KEYUP and ev.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP, pygame.K_z):
                    if self.player.vy < -8:          # variable jump height
                        self.player.vy *= 0.45
            self.update(dt, pygame.key.get_pressed())
            self.draw()
            pygame.display.flip()


if __name__ == "__main__":
    Game().run()
