"""Room loading from text files.

A room file is a grid of tile characters followed by an optional metadata
section separated by a line containing only ``---``. See
``assets/rooms/legend.txt`` for the tile legend.

Metadata lines:
    spawn X Y
    enemy <type> X Y
    door <side> <dest_room> <dest_spawn_side>
"""
from __future__ import annotations

from pathlib import Path

from . import config
from .world import Level

ROOT = Path(__file__).resolve().parents[1]
ROOM_DIR = ROOT / "assets" / "rooms"


class Room(Level):
    """A Level with door metadata and a stable id."""

    def __init__(self, room_id, tiles, enemy_spawns, player_spawn, doors):
        super().__init__(tiles, enemy_spawns, player_spawn)
        self.id = room_id
        self.doors = doors


def _door_rect(side, w, h):
    door_h = 6
    # Side doors sit on the floor (the last three rows are solid) so the
    # player can actually walk into them.
    floor_y = max(0, h - 3 - door_h)
    if side == "left":
        return (0, floor_y, 2, door_h)
    if side == "right":
        return (w - 2, floor_y, 2, door_h)
    if side == "top":
        return ((w - door_h) // 2, 0, door_h, 2)
    if side == "bottom":
        return ((w - door_h) // 2, h - 2, door_h, 2)
    return (0, floor_y, 2, door_h)


def load_room(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if "---" in lines:
        idx = lines.index("---")
        grid_lines = lines[:idx]
        meta_lines = lines[idx + 1:]
    else:
        grid_lines = lines
        meta_lines = []

    while grid_lines and grid_lines[-1].strip() == "":
        grid_lines.pop()

    width = max((len(line) for line in grid_lines), default=0)
    tiles = [list(line.ljust(width)) for line in grid_lines]

    enemy_spawns = []
    player_spawn = (2.0, max(1.0, len(tiles) - 3.0)) if tiles else (2.0, 2.0)
    doors = []

    for raw in meta_lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "spawn" and len(parts) >= 3:
            player_spawn = (float(parts[1]), float(parts[2]))
        elif parts[0] == "enemy" and len(parts) >= 4:
            enemy_spawns.append((parts[1], float(parts[2]), float(parts[3])))
        elif parts[0] == "door" and len(parts) >= 4:
            side, dest, dest_side = parts[1], parts[2], parts[3]
            doors.append({
                "side": side,
                "dest": dest,
                "dest_side": dest_side,
                "rect": _door_rect(side, width, len(tiles)),
            })

    return Room(path.stem, tiles, enemy_spawns, player_spawn, doors)


def load_room_by_id(room_id):
    return load_room(ROOM_DIR / f"{room_id}.txt")
