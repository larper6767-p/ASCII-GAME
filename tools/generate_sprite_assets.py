"""Generate the tiny pixel-art PNG sheets used by the glyph sprite pipeline.

The runtime never needs pygame to *create* these files; it only loads and
converts them. Run this from the repo root after changing the art:

    python tools/generate_sprite_assets.py
"""
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "sprites"


def surface(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def outline_rect(s, color, rect, width=1):
    pygame.draw.rect(s, color, rect, width)


def player_frames():
    """24x36 frames, right-facing: idle, run A, run B, air, attack."""
    frames = []
    for pose in ("idle", "run_a", "run_b", "air", "attack"):
        s = surface(24, 36)
        # Cloak / body silhouette (bright saturated knight blues).
        body = [(8, 10), (16, 10), (19, 28), (16, 32), (8, 32), (5, 28)]
        pygame.draw.polygon(s, (44, 105, 175), body)
        pygame.draw.polygon(s, (70, 150, 215), [(9, 12), (15, 12), (17, 27), (7, 27)])
        # Hood and face.
        pygame.draw.ellipse(s, (36, 80, 135), (6, 3, 12, 14))
        pygame.draw.ellipse(s, (60, 140, 205), (7, 4, 10, 10))
        pygame.draw.ellipse(s, (8, 14, 24), (9, 8, 7, 6))
        s.set_at((11, 11), (210, 250, 255))
        s.set_at((14, 11), (150, 225, 255))
        # Shoulders and arms.
        pygame.draw.rect(s, (85, 170, 225), (5, 14, 4, 8))
        pygame.draw.rect(s, (85, 170, 225), (15, 14, 4, 8))
        # Legs.
        if pose == "run_a":
            pygame.draw.rect(s, (42, 75, 118), (7, 29, 4, 7))
            pygame.draw.rect(s, (42, 75, 118), (14, 27, 4, 7))
            pygame.draw.rect(s, (125, 160, 185), (6, 34, 5, 2))
            pygame.draw.rect(s, (125, 160, 185), (14, 33, 5, 2))
        elif pose == "run_b":
            pygame.draw.rect(s, (42, 75, 118), (9, 28, 4, 8))
            pygame.draw.rect(s, (42, 75, 118), (13, 30, 4, 7))
            pygame.draw.rect(s, (125, 160, 185), (8, 34, 5, 2))
            pygame.draw.rect(s, (125, 160, 185), (13, 35, 5, 2))
        elif pose == "air":
            pygame.draw.rect(s, (42, 75, 118), (7, 28, 4, 5))
            pygame.draw.rect(s, (42, 75, 118), (14, 29, 4, 5))
            pygame.draw.rect(s, (125, 160, 185), (6, 32, 5, 2))
            pygame.draw.rect(s, (125, 160, 185), (14, 33, 5, 2))
            # Flared cloak.
            pygame.draw.polygon(s, (42, 100, 165), [(5, 20), (2, 29), (7, 27)])
        else:
            pygame.draw.rect(s, (42, 75, 118), (8, 29, 4, 7))
            pygame.draw.rect(s, (42, 75, 118), (13, 29, 4, 7))
            pygame.draw.rect(s, (125, 160, 185), (7, 34, 5, 2))
            pygame.draw.rect(s, (125, 160, 185), (13, 34, 5, 2))

        # Sword. Idle/run holds it upright; attack thrusts it forward.
        if pose == "attack":
            pygame.draw.rect(s, (225, 240, 250), (17, 17, 7, 2))
            pygame.draw.polygon(s, (240, 252, 255), [(24, 18), (18, 15), (18, 20)])
            pygame.draw.rect(s, (150, 112, 66), (14, 17, 4, 2))
            pygame.draw.rect(s, (85, 170, 225), (16, 16, 3, 5))
            pygame.draw.polygon(s, (55, 125, 185), [(5, 18), (1, 24), (6, 29)])
        else:
            pygame.draw.rect(s, (215, 232, 245), (18, 12, 2, 16))
            pygame.draw.polygon(s, (240, 252, 255), [(18, 11), (20, 11), (19, 9)])
            pygame.draw.rect(s, (150, 112, 66), (16, 17, 5, 2))
            pygame.draw.rect(s, (85, 170, 225), (17, 20, 3, 5))

        # A few bright cloth pixels keep the silhouette from becoming a blob.
        s.set_at((10, 18), (120, 205, 250))
        s.set_at((12, 21), (120, 205, 250))
        s.set_at((15, 24), (105, 180, 235))
        frames.append(s)
    return frames


def crawler_frames():
    """24x24 frames, right-facing beetle."""
    frames = []
    for step in (0, 1):
        s = surface(24, 24)
        pygame.draw.ellipse(s, (120, 34, 38), (3, 5, 18, 12))
        pygame.draw.ellipse(s, (215, 62, 60), (5, 4, 14, 10))
        pygame.draw.ellipse(s, (248, 112, 98), (7, 5, 9, 5))
        pygame.draw.rect(s, (140, 40, 44), (5, 15, 14, 3))
        # Head and pincers.
        pygame.draw.ellipse(s, (180, 58, 60), (17, 9, 6, 7))
        pygame.draw.circle(s, (255, 235, 130), (20, 11), 1)
        pygame.draw.line(s, (250, 185, 140), (20, 9), (23, 6), 1)
        pygame.draw.line(s, (250, 185, 140), (20, 14), (23, 17), 1)
        # Legs alternate.
        for i, x in enumerate((6, 10, 14, 18)):
            lift = 1 if (i + step) % 2 else 0
            pygame.draw.line(s, (80, 30, 34), (x, 17), (x - 2, 22 - lift), 1)
        frames.append(s)
    return frames


def flyer_frames():
    """40x24 frames, right-facing moth with two wing beats."""
    frames = []
    for beat in (0, 1):
        s = surface(40, 24)
        # Wings.
        if beat == 0:
            left = [(19, 11), (4, 2), (7, 11), (3, 18), (18, 15)]
            right = [(21, 11), (36, 2), (33, 11), (37, 18), (22, 15)]
        else:
            left = [(19, 11), (5, 8), (7, 15), (4, 21), (18, 15)]
            right = [(21, 11), (35, 8), (33, 15), (36, 21), (22, 15)]
        pygame.draw.polygon(s, (140, 78, 185), left)
        pygame.draw.polygon(s, (140, 78, 185), right)
        pygame.draw.polygon(s, (212, 140, 245), [(19, 10), (9, 5), (10, 13), (18, 15)])
        pygame.draw.polygon(s, (212, 140, 245), [(21, 10), (31, 5), (30, 13), (22, 15)])
        pygame.draw.ellipse(s, (100, 55, 135), (16, 7, 8, 13))
        pygame.draw.ellipse(s, (190, 125, 225), (17, 9, 5, 8))
        pygame.draw.circle(s, (255, 235, 130), (24, 11), 1)
        pygame.draw.line(s, (235, 215, 255), (19, 7), (16, 2), 1)
        pygame.draw.line(s, (235, 215, 255), (21, 7), (24, 2), 1)
        frames.append(s)
    return frames


def spitter_frames():
    """24x36 frames, right-facing rooted spitter."""
    frames = []
    for frame in (0, 1):
        s = surface(24, 36)
        # Rooted stem and leaves.
        pygame.draw.rect(s, (55, 125, 68), (11, 18, 4, 16))
        pygame.draw.polygon(s, (88, 185, 98), [(11, 24), (3, 20), (8, 29)])
        pygame.draw.polygon(s, (110, 212, 118), [(14, 21), (21, 17), (17, 28)])
        pygame.draw.ellipse(s, (66, 150, 80), (7, 31, 12, 4))
        # Bulb / cannon body.
        pygame.draw.ellipse(s, (74, 158, 84), (4, 8, 16, 14))
        pygame.draw.ellipse(s, (140, 235, 145), (6, 9, 11, 9))
        pygame.draw.ellipse(s, (195, 255, 195), (8, 10, 5, 4))
        # Cannon barrel.
        pygame.draw.rect(s, (110, 212, 116), (16, 13, 7, 5))
        pygame.draw.rect(s, (215, 255, 215), (21, 14, 3, 3))
        # Opening: changes with the animation frame.
        if frame == 0:
            pygame.draw.circle(s, (26, 66, 34), (18, 15), 2)
        else:
            pygame.draw.circle(s, (26, 66, 34), (18, 15), 3)
            pygame.draw.circle(s, (165, 255, 170), (18, 15), 1)
        # A couple of leaf veins / eyes.
        s.set_at((10, 13), (245, 255, 190))
        s.set_at((12, 13), (245, 255, 190))
        pygame.draw.line(s, (145, 235, 150), (6, 7), (8, 3), 1)
        pygame.draw.line(s, (145, 235, 150), (15, 7), (14, 3), 1)
        frames.append(s)
    return frames


def shot_frames():
    s = surface(8, 12)
    pygame.draw.circle(s, (62, 180, 84), (4, 6), 4)
    pygame.draw.circle(s, (165, 255, 170), (4, 6), 2)
    pygame.draw.circle(s, (240, 255, 215), (4, 6), 1)
    for p in ((1, 2), (6, 3), (2, 9), (7, 8)):
        s.set_at(p, (130, 245, 145))
    return [s]


def save_sheet(name, frames):
    if not frames:
        return
    w, h = frames[0].get_size()
    sheet = surface(w * len(frames), h)
    for i, frame in enumerate(frames):
        sheet.blit(frame, (i * w, 0))
    pygame.image.save(sheet, str(OUT / name))


def main():
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.HIDDEN)
    OUT.mkdir(parents=True, exist_ok=True)
    save_sheet("player.png", player_frames())
    save_sheet("crawler.png", crawler_frames())
    save_sheet("flyer.png", flyer_frames())
    save_sheet("spitter.png", spitter_frames())
    save_sheet("shot.png", shot_frames())
    pygame.quit()
    print(f"wrote sprite sheets to {OUT}")


if __name__ == "__main__":
    main()
