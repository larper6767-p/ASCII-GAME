"""A cheap cached-glow bloom pass for Renderer v2.

Emissive elements are accumulated into a low-resolution additive layer.
Two smooth down/up passes act as a blur; the result is scaled once and added
to the finished frame.  Glow blobs are cached by colour and radius.
"""
from __future__ import annotations

import pygame

from . import config


class Bloom:
    def __init__(self, screen_w, screen_h, scale=config.BLOOM_SCALE):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.scale = max(1, int(scale))
        self.glow_w = max(1, screen_w // self.scale)
        self.glow_h = max(1, screen_h // self.scale)
        self.glow = pygame.Surface((self.glow_w, self.glow_h)).convert()
        self.blur_a = pygame.Surface((max(1, self.glow_w // 2),
                                      max(1, self.glow_h // 2))).convert()
        self.blur_b = pygame.Surface((self.glow_w, self.glow_h)).convert()
        self.scaled = pygame.Surface((screen_w, screen_h)).convert()
        self._blobs = {}
        self._batch = []
        self.stats = {"glows": 0, "blits": 0}

    def begin(self):
        self.glow.fill((0, 0, 0))
        self._batch.clear()
        self.stats["glows"] = 0

    def _blob(self, radius, color):
        key = (int(radius), color)
        cached = self._blobs.get(key)
        if cached is not None:
            return cached
        radius = max(1, int(radius))
        size = radius * 2 + 1
        surf = pygame.Surface((size, size)).convert()
        surf.fill((0, 0, 0))
        for i in range(radius, 0, -1):
            t = 1.0 - (i / radius)
            shade = (
                int(color[0] * t * 0.9),
                int(color[1] * t * 0.9),
                int(color[2] * t * 0.9),
            )
            pygame.draw.circle(surf, shade, (radius, radius), i)
        self._blobs[key] = surf
        return surf

    def add(self, px, py, radius, color, strength=1.0):
        """Queue a glow in *screen pixel* coordinates."""
        gx = int(px / self.scale)
        gy = int(py / self.scale)
        if gx < -radius or gy < -radius or gx > self.glow_w + radius or gy > self.glow_h + radius:
            return
        blob = self._blob(max(1, int(radius / self.scale)), color)
        if strength != 1.0:
            blob = blob.copy()
            blob.fill((int(strength * 255), int(strength * 255), int(strength * 255)),
                      special_flags=pygame.BLEND_RGB_MULT)
        self._batch.append((blob, (gx - blob.get_width() // 2,
                                   gy - blob.get_height() // 2), None,
                            pygame.BLEND_RGB_ADD))

    def finish(self, screen):
        if self._batch:
            self.glow.blits(self._batch, doreturn=False)
            self.stats["blits"] += len(self._batch)
            self.stats["glows"] = len(self._batch)
        else:
            self.stats["glows"] = 0

        # Cached scratch surfaces avoid allocating the same buffers each frame.
        pygame.transform.smoothscale(self.glow, self.blur_a.get_size(),
                                     self.blur_a)
        for _ in range(max(1, config.BLOOM_BLUR_PASSES)):
            pygame.transform.smoothscale(self.blur_a, self.glow.get_size(),
                                         self.blur_b)
            pygame.transform.smoothscale(self.blur_b, self.blur_a.get_size(),
                                         self.blur_a)
        pygame.transform.smoothscale(self.blur_a, self.scaled.get_size(),
                                     self.scaled)
        screen.blit(self.scaled, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        return self.stats
