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
        # Cloak / body silhouette.
        body = [(8, 10), (16, 10), (19, 28), (16, 32), (8, 32), (5, 28)]
        pygame.draw.polygon(s, (28, 60, 100), body)
        pygame.draw.polygon(s, (44, 96, 145), [(9, 12), (15, 12), (17, 27), (7, 27)])
        # Hood and face.
        pygame.draw.ellipse(s, (22, 48, 82), (6, 3, 12, 14))
        pygame.draw.ellipse(s, (38, 92, 135), (7, 4, 10, 10))
        pygame.draw.ellipse(s, (8, 14, 24), (9, 8, 7, 6))
        s.set_at((11, 11), (210, 250, 255))
        s.set_at((14, 11), (150, 225, 255))
        # Shoulders and arms.
        pygame.draw.rect(s, (55, 120, 165), (5, 14, 4, 8))
        pygame.draw.rect(s, (55, 120, 165), (15, 14, 4, 8))
        # Legs.
        if pose == "run_a":
            pygame.draw.rect(s, (25, 45, 70), (7, 29, 4, 7))
            pygame.draw.rect(s, (25, 45, 70), (14, 27, 4, 7))
            pygame.draw.rect(s, (80, 110, 130), (6, 34, 5, 2))
            pygame.draw.rect(s, (80, 110, 130), (14, 33, 5, 2))
        elif pose == "run_b":
            pygame.draw.rect(s, (25, 45, 70), (9, 28, 4, 8))
            pygame.draw.rect(s, (25, 45, 70), (13, 30, 4, 7))
            pygame.draw.rect(s, (80, 110, 130), (8, 34, 5, 2))
            pygame.draw.rect(s, (80, 110, 130), (13, 35, 5, 2))
        elif pose == "air":
            pygame.draw.rect(s, (25, 45, 70), (7, 28, 4, 5))
            pygame.draw.rect(s, (25, 45, 70), (14, 29, 4, 5))
            pygame.draw.rect(s, (80, 110, 130), (6, 32, 5, 2))
            pygame.draw.rect(s, (80, 110, 130), (14, 33, 5, 2))
            # Flared cloak.
            pygame.draw.polygon(s, (26, 58, 95), [(5, 20), (2, 29), (7, 27)])
        else:
            pygame.draw.rect(s, (25, 45, 70), (8, 29, 4, 7))
            pygame.draw.rect(s, (25, 45, 70), (13, 29, 4, 7))
            pygame.draw.rect(s, (80, 110, 130), (7, 34, 5, 2))
            pygame.draw.rect(s, (80, 110, 130), (13, 34, 5, 2))

        # Sword. Idle/run holds it upright; attack thrusts it forward.
        if pose == "attack":
            pygame.draw.rect(s, (205, 225, 235), (17, 17, 7, 2))
            pygame.draw.polygon(s, (235, 250, 255), [(24, 18), (18, 15), (18, 20)])
            pygame.draw.rect(s, (120, 90, 55), (14, 17, 4, 2))
            pygame.draw.rect(s, (55, 120, 165), (16, 16, 3, 5))
            pygame.draw.polygon(s, (35, 80, 120), [(5, 18), (1, 24), (6, 29)])
        else:
            pygame.draw.rect(s, (190, 210, 225), (18, 12, 2, 16))
            pygame.draw.polygon(s, (235, 250, 255), [(18, 11), (20, 11), (19, 9)])
            pygame.draw.rect(s, (120, 90, 55), (16, 17, 5, 2))
            pygame.draw.rect(s, (55, 120, 165), (17, 20, 3, 5))

        # A few bright cloth pixels keep the silhouette from becoming a blob.
        s.set_at((10, 18), (92, 170, 215))
        s.set_at((12, 21), (92, 170, 215))
        s.set_at((15, 24), (80, 145, 195))
        frames.append(s)
    return frames


def crawler_frames():
    """24x24 frames, right-facing beetle."""
    frames = []
    for step in (0, 1):
        s = surface(24, 24)
        pygame.draw.ellipse(s, (70, 20, 24), (3, 5, 18, 12))
        pygame.draw.ellipse(s, (155, 42, 48), (5, 4, 14, 10))
        pygame.draw.ellipse(s, (205, 75, 68), (7, 5, 9, 5))
        pygame.draw.rect(s, (85, 22, 26), (5, 15, 14, 3))
        # Head and pincers.
        pygame.draw.ellipse(s, (120, 35, 40), (17, 9, 6, 7))
        pygame.draw.circle(s, (255, 225, 120), (20, 11), 1)
        pygame.draw.line(s, (225, 150, 110), (20, 9), (23, 6), 1)
        pygame.draw.line(s, (225, 150, 110), (20, 14), (23, 17), 1)
        # Legs alternate.
        for i, x in enumerate((6, 10, 14, 18)):
            lift = 1 if (i + step) % 2 else 0
            pygame.draw.line(s, (45, 16, 20), (x, 17), (x - 2, 22 - lift), 1)
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
        pygame.draw.polygon(s, (92, 48, 120), left)
        pygame.draw.polygon(s, (92, 48, 120), right)
        pygame.draw.polygon(s, (165, 92, 205), [(19, 10), (9, 5), (10, 13), (18, 15)])
        pygame.draw.polygon(s, (165, 92, 205), [(21, 10), (31, 5), (30, 13), (22, 15)])
        pygame.draw.ellipse(s, (60, 30, 80), (16, 7, 8, 13))
        pygame.draw.ellipse(s, (140, 78, 170), (17, 9, 5, 8))
        pygame.draw.circle(s, (255, 225, 120), (24, 11), 1)
        pygame.draw.line(s, (220, 190, 255), (19, 7), (16, 2), 1)
        pygame.draw.line(s, (220, 190, 255), (21, 7), (24, 2), 1)
        frames.append(s)
    return frames


def spitter_frames():
    """24x36 frames, right-facing rooted spitter."""
    frames = []
    for frame in (0, 1):
        s = surface(24, 36)
        # Rooted stem and leaves.
        pygame.draw.rect(s, (35, 78, 45), (11, 18, 4, 16))
        pygame.draw.polygon(s, (55, 125, 65), [(11, 24), (3, 20), (8, 29)])
        pygame.draw.polygon(s, (70, 150, 75), [(14, 21), (21, 17), (17, 28)])
        pygame.draw.ellipse(s, (42, 95, 52), (7, 31, 12, 4))
        # Bulb / cannon body.
        pygame.draw.ellipse(s, (46, 100, 55), (4, 8, 16, 14))
        pygame.draw.ellipse(s, (95, 190, 100), (6, 9, 11, 9))
        pygame.draw.ellipse(s, (150, 235, 150), (8, 10, 5, 4))
        # Cannon barrel.
        pygame.draw.rect(s, (70, 150, 78), (16, 13, 7, 5))
        pygame.draw.rect(s, (175, 255, 175), (21, 14, 3, 3))
        # Opening: changes with the animation frame.
        if frame == 0:
            pygame.draw.circle(s, (20, 50, 26), (18, 15), 2)
        else:
            pygame.draw.circle(s, (20, 50, 26), (18, 15), 3)
            pygame.draw.circle(s, (130, 255, 140), (18, 15), 1)
        # A couple of leaf veins / eyes.
        s.set_at((10, 13), (245, 255, 190))
        s.set_at((12, 13), (245, 255, 190))
        pygame.draw.line(s, (105, 200, 110), (6, 7), (8, 3), 1)
        pygame.draw.line(s, (105, 200, 110), (15, 7), (14, 3), 1)
        frames.append(s)
    return frames


def shot_frames():
    s = surface(8, 12)
    pygame.draw.circle(s, (40, 120, 55), (4, 6), 4)
    pygame.draw.circle(s, (150, 255, 155), (4, 6), 2)
    pygame.draw.circle(s, (235, 255, 210), (4, 6), 1)
    for p in ((1, 2), (6, 3), (2, 9), (7, 8)):
        s.set_at(p, (100, 225, 120))
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
