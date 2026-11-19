"""ASCII sprite art. All art is right-facing; mirror() flips it for left."""

FLIP_TABLE = str.maketrans("/\\()<>[]", "\\/)(><][")


def mirror(lines):
    """Return the left-facing version of a right-facing sprite."""
    return [line[::-1].translate(FLIP_TABLE) for line in lines]


PLAYER_IDLE = (" o ", "/|\\", "/ \\")
PLAYER_RUN = (
    (" o ", "/|\\", "/ |"),
    (" o ", "/|\\", "| \\"),
)
PLAYER_AIR = (" o ", "\\|/", "/ \\")
PLAYER_ATTACK = (" o ", "/|>", "/ \\")
SLASH = ("  \\ ", "   )", "  / ")
SLASH_DOWN = (" | ", "\\|/", " v ")

CRAWLER_FRAMES = (
    ("/^\\", "<_>"),
    ("/^\\", ">_<"),
)

FLYER_FRAMES = (
    ("\\ ^ /", " <o> "),
    ("/ v \\", " <o> "),
)

SPITTER_FRAMES = (
    (" ^ ", "(o>", "/|\\"),
    (" ^ ", "(O>", "/|\\"),
)

# Boss art is drawn directly at glyph resolution (2 glyph cells per physics
# cell, matching BOSS_DATA's 9x4 body). 'o' cells get the eye colour.
BOSS_FRAME = (
    "   ▄▄▄▄▄▄▄▄▄▄▄▄   ",
    "  ██████████████  ",
    " ████oo████oo████ ",
    " ████████████████ ",
    " ████  ████  ████ ",
    "  ██████████████  ",
    "   ▀███    ███▀   ",
    "    ▀▀      ▀▀    ",
)
