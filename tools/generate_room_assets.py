"""Generate the three M5/M6 test rooms as text files.

Run from the repo root:

    python tools/generate_room_assets.py
"""
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "rooms"


def build(w, h, platforms, enemies, doors, spawns, torches=(), extra_meta=(),
          seed=7):
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
    # Torches: non-solid, drawn as flickering flames and light sources.
    for x, y in torches:
        if 0 <= x < w and 0 <= y < h and g[y][x] not in "#=":
            g[y][x] = "T"
    lines = ["".join(row) for row in g]
    meta = list(extra_meta)
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
            torches=[(10, 24), (25, 16), (34, 24), (57, 24),
                     (83, 16), (88, 24), (112, 24)],
            extra_meta=[
                "atmosphere dusk",
                "palette #191426 #8a7a72 #ffb15e",
                "fog 0.85",
                "ember #ff8a4c",
            ],
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
            torches=[(9, 24), (23, 15), (34, 24), (62, 24),
                     (84, 16), (90, 24), (120, 24)],
            extra_meta=[
                "atmosphere ruins",
                "palette #0e1524 #6c7f9a #8fe0ff",
                "fog 1.0",
                "ember #9fd7ff",
            ],
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
            torches=[(9, 24), (21, 16), (31, 24), (56, 24),
                     (82, 16), (86, 24), (102, 24)],
            extra_meta=[
                "atmosphere emberfall",
                "palette #1c0f18 #9a5a4a #ff6a3c",
                "fog 0.6",
                "ember #ff5a3c",
                # Boss arena: doors stay sealed until every enemy is dead.
                "lock_on_enter",
            ],
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
#   T   torch / fire (non-solid, emits flickering light)
#
# Metadata (after a line containing only ---):
#   spawn X Y
#   enemy <type> X Y     (type: crawler, flyer, spitter)
#   door <side> <dest_room> <dest_spawn_side>
#       side / dest_spawn_side: left, right, top, bottom
#   atmosphere <name>    (label for the room mood)
#   palette <sky> <rock> <accent>
#       three #rrggbb colours: sky fill, terrain tint, torch/accent glow
#   fog <0.0..1.0>       (fog density; 0 disables the bank and strips)
#   ember <#rrggbb>      (ambient ember mote colour)
#   lock_on_enter        (seal every door until the room is cleared)
"""
    (OUT / "legend.txt").write_text(legend, encoding="utf-8")
    print(f"wrote {OUT / 'legend.txt'}")


if __name__ == "__main__":
    main()
