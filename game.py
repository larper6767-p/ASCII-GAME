"""Emberfall entry point.

Run: python game.py
Controls: A/D or arrows = move | SPACE/W/Z/UP/K = jump | J = attack
          S/DOWN + J in air = pogo | R = restart | ESC = quit
          F3 = frame stats | F4 = raw input debug
Key bindings are rebindable in assets/keybinds.json (or the path in
EMBERFALL_KEYBINDS).
"""
from emberfall.engine import main


if __name__ == "__main__":
    main()
