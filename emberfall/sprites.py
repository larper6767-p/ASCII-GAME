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
