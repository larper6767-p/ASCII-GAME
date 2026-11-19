"""Generate the three M5 test rooms as text files.

Run from the repo root:

    python tools/generate_room_assets.py
"""
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "rooms"


def build(w, h, platforms, enemies, doors, spawns, seed=7):
    rng = random.Random(seed)
    g = [["."] * w for _ in range(h)]
    # Floor and side walls.
    for x in range(w):
        for yy in (h - 3, h - 2, h - 1):
            g[yy][x] = "#"
    for y in range(h):
        g[y][0] = "#"
        g[y][w - 1] = "#"
    # Platforms with occasional grass on top.
    for x, y, ww in platforms:
        for i in range(ww):
            if 0 <= x + i < w and 0 <= y < h:
                g[y][x + i] = "="
                if y - 1 >= 0 and rng.random() < 0.45:
                    g[y - 1][x + i] = '"'
    lines = ["".join(row) for row in g]
    meta = []
    for x, y in spawns:
        meta.append(f"spawn {x} {y}")
    for kind, x, y in enemies:
        meta.append(f"enemy {kind} {x} {y}")
    for side, dest, dest_side in doors:
        meta.append(f"door {side} {dest} {dest_side}")
    return "\n".join(lines) + "\n---\n" + "\n".join(meta) + "\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    rooms = {
        "room1": build(
            120, 28,
            platforms=[(8, 21, 9), (22, 17, 8), (38, 21, 8), (52, 16, 6),
                       (64, 21, 10), (80, 17, 9), (96, 21, 8),
                       (108, 15, 6)],
            enemies=[("crawler", 18, 22), ("flyer", 26, 14),
                     ("spitter", 47, 22), ("crawler", 68, 22),
                     ("flyer", 84, 13), ("spitter", 100, 22)],
            doors=[("right", "room2", "left")],
            spawns=[(4, 22)],
            seed=1,
        ),
        "room2": build(
            130, 28,
            platforms=[(6, 20, 10), (20, 16, 8), (36, 20, 10),
                       (52, 15, 8), (66, 21, 8), (80, 17, 10),
                       (96, 20, 9), (112, 15, 7)],
            enemies=[("crawler", 17, 22), ("flyer", 24, 13),
                     ("flyer", 44, 12), ("spitter", 47, 22),
                     ("crawler", 30, 22), ("crawler", 84, 22),
                     ("flyer", 100, 13), ("spitter", 116, 22)],
            doors=[("left", "room1", "right"), ("right", "room3", "left")],
            spawns=[(4, 22)],
            seed=2,
        ),
        "room3": build(
            110, 28,
            platforms=[(6, 21, 8), (18, 17, 8), (32, 21, 8), (46, 16, 9),
                       (62, 21, 8), (78, 17, 9), (94, 21, 8)],
            enemies=[("crawler", 15, 22), ("flyer", 20, 14),
                     ("spitter", 41, 22), ("crawler", 27, 22),
                     ("flyer", 30, 13), ("crawler", 68, 22),
                     ("flyer", 84, 13), ("spitter", 98, 22)],
            doors=[("left", "room2", "right")],
            spawns=[(4, 22)],
            seed=3,
        ),
    }
    for name, content in rooms.items():
        path = OUT / f"{name}.txt"
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path}")

    legend = """# Room legend (one character per tile)
#   #   solid ground / wall
#   =   platform
#   \"   decorative grass (on top of solid ground)
#   .   empty air
#
# Metadata (after a line containing only ---):
#   spawn X Y
#   enemy <type> X Y     (type: crawler, flyer, spitter)
#   door <side> <dest_room> <dest_spawn_side>
#       side / dest_spawn_side: left, right, top, bottom
"""
    (OUT / "legend.txt").write_text(legend, encoding="utf-8")
    print(f"wrote {OUT / 'legend.txt'}")


if __name__ == "__main__":
    main()
