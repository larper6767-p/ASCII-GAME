"""Room loading from text files.

A room file is a grid of tile characters followed by an optional metadata
section separated by a line containing only ``---``. See
``assets/rooms/legend.txt`` for the tile legend.

Metadata lines:
    spawn X Y
    enemy <type> X Y
    door <side> <dest_room> <dest_spawn_side>
    atmosphere <name>
    palette <sky_hex> <rock_hex> <accent_hex>
    fog <0.0..1.0>
    ember <hex>
    lock_on_enter

Malformed rooms raise :class:`RoomError` with the file name and the exact
problem (ragged rows, missing spawn, unknown door destination, ...).
"""
from __future__ import annotations

import math
from pathlib import Path

from . import config
from .physics import collides
from .world import Level

ROOT = Path(__file__).resolve().parents[1]
ROOM_DIR = ROOT / "assets" / "rooms"

# Tile legend. Keep in sync with assets/rooms/legend.txt.
LEGEND = {
    "#": "solid ground / wall",
    "=": "platform",
    '"': "decorative grass",
    ".": "empty air",
    " ": "empty air",
    "T": "torch / fire (non-solid, emits flickering light)",
}

VALID_SIDES = ("left", "right", "top", "bottom")


class RoomError(ValueError):
    """A room file is missing required data or is malformed."""


class Room(Level):
    """A Level with door, atmosphere and lock metadata and a stable id."""

    def __init__(self, room_id, tiles, enemy_spawns, player_spawn, doors,
                 atmosphere=None, lock_on_enter=False):
        super().__init__(tiles, enemy_spawns, player_spawn)
        self.id = room_id
        self.doors = doors
        self.atmosphere = atmosphere or config.default_atmosphere()
        self.lock_on_enter = bool(lock_on_enter)


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


def _parse_pair(parts, path, what):
    try:
        return float(parts[1]), float(parts[2])
    except (ValueError, IndexError) as exc:
        raise RoomError(
            f"{path.name}: {what} needs numeric X Y, got "
            f"{' '.join(parts[1:])!r}"
        ) from exc


def _parse_hex(value, path, what):
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    elif text.lower().startswith("0x"):
        text = text[2:]
    if len(text) != 6:
        raise RoomError(
            f"{path.name}: {what} must be a #rrggbb colour, got {value!r}"
        )
    try:
        return (
            int(text[0:2], 16),
            int(text[2:4], 16),
            int(text[4:6], 16),
        )
    except ValueError as exc:
        raise RoomError(
            f"{path.name}: {what} must be a #rrggbb colour, got {value!r}"
        ) from exc


def _split_sections(text, path):
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
    if not grid_lines:
        raise RoomError(f"{path.name}: room grid is empty")
    return grid_lines, meta_lines


def _parse_grid(grid_lines, path):
    width = len(grid_lines[0])
    if width == 0:
        raise RoomError(f"{path.name}: room grid has zero width")

    allowed = set(LEGEND)
    for number, line in enumerate(grid_lines, 1):
        if len(line) != width:
            raise RoomError(
                f"{path.name}: row {number} has {len(line)} columns, "
                f"expected {width} (ragged room grid)"
            )
        unknown = sorted(set(line) - allowed)
        if unknown:
            raise RoomError(
                f"{path.name}: row {number} uses unknown tile(s) "
                f"{unknown!r}; see assets/rooms/legend.txt"
            )
    return [list(line) for line in grid_lines]


def _parse_metadata(meta_lines, path, width, height):
    enemy_spawns = []
    player_spawn = None
    door_specs = []
    atmosphere = config.default_atmosphere()
    lock_on_enter = False

    for raw in meta_lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        command = parts[0]

        if command == "spawn":
            if len(parts) != 3:
                raise RoomError(
                    f"{path.name}: 'spawn' needs exactly X Y, got {line!r}"
                )
            if player_spawn is not None:
                raise RoomError(f"{path.name}: duplicate 'spawn' line")
            player_spawn = _parse_pair(parts, path, "spawn")
        elif command == "enemy":
            if len(parts) != 4:
                raise RoomError(
                    f"{path.name}: 'enemy' needs <type> X Y, got {line!r}"
                )
            kind = parts[1]
            if kind not in config.ENEMY_DATA:
                raise RoomError(
                    f"{path.name}: unknown enemy type {kind!r}; "
                    f"known types: {', '.join(sorted(config.ENEMY_DATA))}"
                )
            x, y = _parse_pair(parts[1:], path, "enemy")
            enemy_spawns.append((kind, x, y))
        elif command == "door":
            if len(parts) != 4:
                raise RoomError(
                    f"{path.name}: 'door' needs "
                    f"<side> <dest_room> <dest_side>, got {line!r}"
                )
            side, dest, dest_side = parts[1], parts[2], parts[3]
            if side not in VALID_SIDES:
                raise RoomError(
                    f"{path.name}: door side {side!r} must be one of "
                    f"{', '.join(VALID_SIDES)}"
                )
            if dest_side not in VALID_SIDES:
                raise RoomError(
                    f"{path.name}: door destination side {dest_side!r} must "
                    f"be one of {', '.join(VALID_SIDES)}"
                )
            door_specs.append((side, dest, dest_side))
        elif command == "atmosphere":
            if len(parts) != 2:
                raise RoomError(
                    f"{path.name}: 'atmosphere' needs a name, got {line!r}"
                )
            atmosphere["name"] = parts[1]
        elif command == "palette":
            if len(parts) != 4:
                raise RoomError(
                    f"{path.name}: 'palette' needs <sky> <rock> <accent> "
                    f"hex colours, got {line!r}"
                )
            atmosphere["sky"] = _parse_hex(parts[1], path, "palette sky")
            atmosphere["rock"] = _parse_hex(parts[2], path, "palette rock")
            atmosphere["accent"] = _parse_hex(
                parts[3], path, "palette accent"
            )
        elif command == "fog":
            if len(parts) != 2:
                raise RoomError(
                    f"{path.name}: 'fog' needs a density, got {line!r}"
                )
            try:
                density = float(parts[1])
            except ValueError as exc:
                raise RoomError(
                    f"{path.name}: fog density must be a number, "
                    f"got {parts[1]!r}"
                ) from exc
            if not math.isfinite(density) or not 0.0 <= density <= 1.0:
                raise RoomError(
                    f"{path.name}: fog density must be between 0.0 and 1.0, "
                    f"got {density:g}"
                )
            atmosphere["fog"] = density
        elif command == "ember":
            if len(parts) != 2:
                raise RoomError(
                    f"{path.name}: 'ember' needs a hex colour, got {line!r}"
                )
            atmosphere["ember"] = _parse_hex(parts[1], path, "ember")
        elif command == "lock_on_enter":
            if len(parts) != 1:
                raise RoomError(
                    f"{path.name}: 'lock_on_enter' takes no arguments, "
                    f"got {line!r}"
                )
            lock_on_enter = True
        else:
            raise RoomError(
                f"{path.name}: unknown metadata command {command!r}"
            )

    if player_spawn is None:
        raise RoomError(f"{path.name}: missing 'spawn X Y' line")

    for side, dest, dest_side in door_specs:
        target = path.parent / f"{dest}.txt"
        if not target.is_file():
            raise RoomError(
                f"{path.name}: door {side!r} points to missing room "
                f"{dest!r} (expected {target.name})"
            )

    doors = [{
        "side": side,
        "dest": dest,
        "dest_side": dest_side,
        "rect": _door_rect(side, width, height),
    } for side, dest, dest_side in door_specs]
    return enemy_spawns, player_spawn, doors, atmosphere, lock_on_enter


def _validate_spawns(room, path):
    width, height = room.width, room.height
    px, py = room.player_spawn
    if not (0 <= px and px + config.PLAYER_W <= width
            and 0 <= py and py + config.PLAYER_H <= height):
        raise RoomError(
            f"{path.name}: spawn ({px:g}, {py:g}) is outside the room"
        )
    if collides(room, px, py, config.PLAYER_W, config.PLAYER_H):
        raise RoomError(
            f"{path.name}: spawn ({px:g}, {py:g}) overlaps solid tiles"
        )

    for number, (kind, x, y) in enumerate(room.enemy_spawns, 1):
        data = config.ENEMY_DATA[kind]
        if not math.isfinite(x) or not math.isfinite(y):
            raise RoomError(
                f"{path.name}: enemy {number} ({kind}) has non-finite "
                f"coordinates ({x}, {y})"
            )
        if not (0 <= x and x + data["w"] <= width
                and 0 <= y and y + data["h"] <= height):
            raise RoomError(
                f"{path.name}: enemy {number} ({kind}) at ({x:g}, {y:g}) "
                f"is outside the room"
            )
        if collides(room, x, y, data["w"], data["h"]):
            raise RoomError(
                f"{path.name}: enemy {number} ({kind}) at ({x:g}, {y:g}) "
                f"overlaps solid tiles"
            )


def load_room(path):
    path = Path(path)
    if not path.is_file():
        raise RoomError(f"room file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RoomError(f"{path.name}: cannot read room file: {exc}") from exc

    grid_lines, meta_lines = _split_sections(text, path)
    tiles = _parse_grid(grid_lines, path)
    height = len(tiles)
    width = len(tiles[0])
    enemy_spawns, player_spawn, doors, atmosphere, lock_on_enter = (
        _parse_metadata(meta_lines, path, width, height)
    )
    room = Room(
        path.stem, tiles, enemy_spawns, player_spawn, doors,
        atmosphere, lock_on_enter,
    )
    _validate_spawns(room, path)
    return room


def load_room_by_id(room_id):
    path = ROOM_DIR / f"{room_id}.txt"
    if not path.is_file():
        raise RoomError(
            f"unknown room {room_id!r}: {path} does not exist"
        )
    return load_room(path)
