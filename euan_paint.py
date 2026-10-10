#!/usr/bin/env python3
"""Euan Paint - a toddler-proof painting app.

Mouse:
  left button / middle button   paint, stamp
  scroll wheel                  change colour
  right button                  next stamp shape
Keyboard: every key stamps a random shape somewhere on the page.

Grown-ups: hold Ctrl + Shift + Q (and nothing else) for 3 seconds to exit.
Pictures are saved automatically to ~/Pictures/Euan Paint when the page is
cleared and when the app exits.
"""
import argparse
import bisect
import math
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

# These must be set before SDL starts.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0")
os.environ.setdefault("SDL_GRAB_KEYBOARD", "1")
os.environ.setdefault("SDL_ALLOW_ALT_TAB_WHILE_GRABBED", "0")
# Windows: draw at the real screen resolution instead of letting display scaling blur it.
os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")

import pygame

SAVE_DIR = Path.home() / "Pictures" / "Euan Paint"
EXIT_HOLD_SECONDS = 3.0

WHITE = (255, 255, 255)
INK = (35, 30, 40)

PALETTE = [
    ("red", (235, 45, 45)),
    ("orange", (255, 140, 0)),
    ("yellow", (255, 214, 0)),
    ("light green", (130, 215, 40)),
    ("green", (20, 160, 70)),
    ("turquoise", (0, 195, 195)),
    ("light blue", (60, 170, 255)),
    ("blue", (35, 70, 225)),
    ("purple", (140, 60, 210)),
    ("pink", (255, 105, 180)),
    ("brown", (140, 85, 40)),
    ("grey", (150, 150, 150)),
    ("black", (25, 25, 25)),
    ("white", (255, 255, 255)),
]
RAINBOW = [(230, 40, 40), (255, 140, 0), (255, 215, 0), (60, 190, 60),
           (40, 140, 255), (70, 60, 200), (150, 70, 210)]
SIZES = [
    dict(brush=7, stripe=4, stamp=70, eraser=16, gauge=11),
    dict(brush=16, stripe=7, stamp=110, eraser=32, gauge=16),
    dict(brush=30, stripe=11, stamp=160, eraser=56, gauge=24),
]
STAMPS = ["star", "heart", "smiley", "flower", "sun",
          "fish", "car", "train", "butterfly", "rocket"]
TOOLS = ["brush", "rainbow", "railway", "glitter", "bucket", "eraser", "size", "undo", "clear"]
UNDO_STEPS = 20
GOLD = (255, 205, 40)

CTRL_KEYS = {pygame.K_LCTRL, pygame.K_RCTRL}
SHIFT_KEYS = {pygame.K_LSHIFT, pygame.K_RSHIFT}
MODIFIER_KEYS = CTRL_KEYS | SHIFT_KEYS | {
    getattr(pygame, name) for name in
    ("K_LALT", "K_RALT", "K_LMETA", "K_RMETA", "K_LGUI", "K_RGUI",
     "K_LSUPER", "K_RSUPER", "K_CAPSLOCK", "K_NUMLOCK", "K_MODE")
    if hasattr(pygame, name)}


# ---------------------------------------------------------------- helpers

def darker(c, f=0.55):
    return tuple(int(x * f) for x in c[:3])


def lighter(c, f=0.5):
    return tuple(int(x + (255 - x) * f) for x in c[:3])


def luma(c):
    return 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]


def ease_out_back(t):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def draw_sparkle(s, color, center, r, angle=0.0):
    """Four-pointed twinkle star."""
    cx, cy = center
    pts = []
    for i in range(8):
        a = angle + i * math.pi / 4
        rr = r if i % 2 == 0 else r * 0.28
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    pygame.draw.polygon(s, color, pts)


def rotated_rect_points(cx, cy, w, h, angle):
    ca, sa = math.cos(angle), math.sin(angle)
    pts = []
    for x, y in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        pts.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return pts


# ----------------------------------------------------------------- drawing

def draw_train(s, ox, oy, k, color):
    """Cartoon steam engine facing right, in a 200 x 140 design box scaled by k."""
    def R(x, y, w, h):
        return pygame.Rect(round(ox + x * k), round(oy + y * k),
                           max(1, round(w * k)), max(1, round(h * k)))

    def P(x, y):
        return (ox + x * k, oy + y * k)

    ow = max(1, round(3 * k))
    br = max(1, round(6 * k))
    dark = darker(color)
    catcher = [P(170, 96), P(198, 126), P(158, 126)]
    pygame.draw.polygon(s, dark, catcher)
    pygame.draw.polygon(s, INK, catcher, ow)
    pygame.draw.circle(s, (255, 200, 40), P(112, 54), 13 * k)
    pygame.draw.circle(s, INK, P(112, 54), 13 * k, ow)
    for rect in (R(140, 22, 18, 34), R(133, 14, 32, 11)):
        pygame.draw.rect(s, dark, rect, border_radius=br // 2)
        pygame.draw.rect(s, INK, rect, ow, border_radius=br // 2)
    for rect, col in ((R(72, 50, 102, 50), color), (R(14, 26, 64, 74), color),
                      (R(6, 18, 80, 12), dark), (R(28, 38, 36, 28), (170, 225, 255)),
                      (R(8, 96, 174, 14), dark)):
        pygame.draw.rect(s, col, rect, border_radius=br)
        pygame.draw.rect(s, INK, rect, ow, border_radius=br)
    pygame.draw.circle(s, (235, 235, 235), P(172, 74), 24 * k)
    pygame.draw.circle(s, INK, P(172, 74), 24 * k, ow)
    pygame.draw.circle(s, INK, P(165, 68), 3.5 * k)
    pygame.draw.circle(s, INK, P(180, 68), 3.5 * k)
    pygame.draw.arc(s, INK, R(160, 68, 24, 16), math.pi + 0.3, 2 * math.pi - 0.3,
                    max(1, round(2.5 * k)))
    for x in (44, 94, 144):
        pygame.draw.circle(s, INK, P(x, 112), 20 * k)
    pygame.draw.line(s, (190, 190, 200), P(44, 112), P(144, 112), max(1, round(5 * k)))
    for x in (44, 94, 144):
        pygame.draw.circle(s, (190, 190, 200), P(x, 112), 8 * k)


def draw_carriage(s, ox, oy, k, color):
    """Cartoon passenger carriage in the same 200 x 140 design box as the engine."""
    def R(x, y, w, h):
        return pygame.Rect(round(ox + x * k), round(oy + y * k),
                           max(1, round(w * k)), max(1, round(h * k)))

    ow = max(1, round(3 * k))
    br = max(1, round(8 * k))
    pygame.draw.line(s, INK, (ox, oy + 104 * k), (ox + 200 * k, oy + 104 * k), max(1, round(5 * k)))
    for rect, col in ((R(10, 40, 180, 64), color), (R(4, 28, 192, 16), darker(color))):
        pygame.draw.rect(s, col, rect, border_radius=br)
        pygame.draw.rect(s, INK, rect, ow, border_radius=br)
    for x in (24, 82, 140):
        win = R(x, 52, 36, 26)
        pygame.draw.rect(s, (170, 225, 255), win, border_radius=br // 2)
        pygame.draw.rect(s, INK, win, ow, border_radius=br // 2)
    for x in (52, 148):
        pygame.draw.circle(s, INK, (ox + x * k, oy + 112 * k), 18 * k)
        pygame.draw.circle(s, (190, 190, 200), (ox + x * k, oy + 112 * k), 7 * k)


def make_carriage_sprite(width, color):
    height = round(width * 0.7)
    big = pygame.Surface((width * 2, height * 2), pygame.SRCALPHA)
    draw_carriage(big, 0, 0, width * 2 / 200, color)
    return pygame.transform.smoothscale(big, (width, height))


SLEEPER = (150, 100, 60)
RAIL = (95, 100, 115)
RAIL_SHINE = (205, 210, 222)


def draw_track(s, pts, heads, gauge, start=0, offset=(0, 0), phase=0):
    """Railway track along pts: sleepers every 16 px, then two steel rails on top.

    phase shifts which points get sleepers, so redrawing part of a track whose
    points were renumbered lands the sleepers in the same places."""
    ox, oy = offset
    half = gauge / 2
    for i in range(start, len(pts)):
        if (i - phase) % 4:
            continue
        (x, y), (tx, ty) = pts[i], heads[i]
        x, y = x + ox, y + oy
        a, c = gauge * 0.22, gauge * 0.85
        sleeper = [(x + tx * a - ty * c, y + ty * a + tx * c), (x - tx * a - ty * c, y - ty * a + tx * c),
                   (x - tx * a + ty * c, y - ty * a - tx * c), (x + tx * a + ty * c, y + ty * a - tx * c)]
        pygame.draw.polygon(s, SLEEPER, sleeper)
        pygame.draw.polygon(s, darker(SLEEPER, 0.7), sleeper, 1)
    seg = range(max(0, start - 1), len(pts))
    if len(seg) < 2:
        return
    width = max(2, round(gauge / 5))
    for side in (-1, 1):
        rail = [(pts[i][0] + ox - heads[i][1] * half * side, pts[i][1] + oy + heads[i][0] * half * side)
                for i in seg]
        pygame.draw.lines(s, RAIL, False, rail, width)
        pygame.draw.lines(s, RAIL_SHINE, False, rail, max(1, width // 3))


TUNNEL_ANCHOR = (0.36, 0.76)  # where the track ends, deep inside the opening
TUNNEL_SIZE = 10               # tunnel width in track gauges


def make_tunnel_sprites(width):
    """Upright grassy hill with a stone tunnel mouth on its left, in a 100 x 80 design box.

    The track runs in level from the left. Returns (front, interior): the
    interior is the dark inside of the tunnel, painted under the track and
    trains; the front is the hill and arch with a see-through opening that gets
    darker the deeper it goes, drawn over them so trains roll into the dark.
    Flip both horizontally for a tunnel that faces right.
    """
    height = round(width * 0.8)
    W, H = width * 2, height * 2
    k = W / 100

    def P(x, y):
        return (x * k, y * k)

    def R(x, y, w, h):
        return pygame.Rect(round(x * k), round(y * k), round(w * k), round(h * k))

    def opening(surf, col):
        pygame.draw.circle(surf, col, P(24, 52), 18 * k, draw_top_left=True, draw_top_right=True)
        pygame.draw.rect(surf, col, R(6, 52, 36, 29))

    ow = max(2, round(1.6 * k))
    grass, grass_dark = (120, 195, 85), (70, 140, 55)
    stone, stone_dark = (175, 170, 165), (105, 100, 98)
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.ellipse(s, grass, R(2, 6, 104, 150))
    pygame.draw.ellipse(s, grass_dark, R(2, 6, 104, 150), ow)
    for x, y in ((60, 22), (84, 34), (74, 56), (90, 70), (46, 14)):
        pygame.draw.arc(s, grass_dark, R(x - 3, y - 2, 6, 6), math.pi * 0.1, math.pi * 0.9, ow)
    for (x, y), col in (((66, 34), (255, 215, 0)), ((86, 52), (255, 120, 180)),
                        ((58, 66), (255, 255, 255)), ((78, 20), (255, 140, 0))):
        pygame.draw.circle(s, col, P(x, y), 2.6 * k)
        pygame.draw.circle(s, darker(col), P(x, y), 2.6 * k, max(1, ow // 2))
    # Stone arch over the opening, standing on a pillar on the deep (right) side.
    pygame.draw.circle(s, stone, P(24, 52), 27 * k, draw_top_left=True, draw_top_right=True)
    pygame.draw.rect(s, stone, R(42, 52, 9, 29))
    pygame.draw.circle(s, stone_dark, P(24, 52), 27 * k, ow, draw_top_left=True, draw_top_right=True)
    pygame.draw.line(s, stone_dark, P(51, 52), P(51, 80), ow)
    for i in range(7):
        ang = math.pi * i / 6
        pygame.draw.line(s, stone_dark, P(24 + 18 * math.cos(ang), 52 - 18 * math.sin(ang)),
                         P(24 + 27 * math.cos(ang), 52 - 27 * math.sin(ang)), ow)
    for y in (60, 70):
        pygame.draw.line(s, stone_dark, P(42, y), P(51, y), ow)
    # Cut out the opening, plus a clear way in on the left so arriving trains
    # stay in view until they reach the dark.
    opening(s, (0, 0, 0, 0))
    pygame.draw.rect(s, (0, 0, 0, 0), R(0, 44, 7, 37))
    shade = pygame.Surface((W, H), pygame.SRCALPHA)
    for x in range(W):
        depth = max(0.0, min(1.0, (x / k - 8) / 30))
        pygame.draw.line(shade, (20, 15, 25, round(255 * depth ** 1.2)), (x, 0), (x, H))
    mask = pygame.Surface((W, H), pygame.SRCALPHA)
    opening(mask, (255, 255, 255, 255))
    shade.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    s.blit(shade, (0, 0))
    pygame.draw.circle(s, stone_dark, P(24, 52), 18 * k, ow, draw_top_left=True, draw_top_right=True)
    pygame.draw.line(s, stone_dark, P(42, 52), P(42, 80), ow)

    inside = pygame.Surface((W, H), pygame.SRCALPHA)
    opening(inside, (70, 60, 75, 255))
    size = (width, height)
    return pygame.transform.smoothscale(s, size), pygame.transform.smoothscale(inside, size)


def make_train_sprite(width, color=(230, 40, 40)):
    height = round(width * 0.7)
    big = pygame.Surface((width * 2, height * 2), pygame.SRCALPHA)
    draw_train(big, 0, 0, width * 2 / 200, color)
    return pygame.transform.smoothscale(big, (width, height))


def render_stamp(shape, color, size):
    """Render a stamp at 2x and scale down, which gives smooth edges."""
    S = size * 2
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    u = S / 100
    dark = darker(color)
    feature = WHITE if luma(color) < 90 else INK
    ow = max(2, round(2.6 * u))

    def P(x, y):
        return (x * u, y * u)

    def R(x, y, w, h):
        return pygame.Rect(round(x * u), round(y * u), round(w * u), round(h * u))

    def poly(col, pts):
        pygame.draw.polygon(s, col, pts)
        pygame.draw.polygon(s, dark, pts, ow)

    def circle(col, x, y, r, outline=True):
        pygame.draw.circle(s, col, P(x, y), r * u)
        if outline:
            pygame.draw.circle(s, dark, P(x, y), r * u, ow)

    def ellipse(col, rect, outline=True):
        pygame.draw.ellipse(s, col, rect)
        if outline:
            pygame.draw.ellipse(s, dark, rect, ow)

    def face(cx, cy, k=1.0):
        pygame.draw.circle(s, feature, P(cx - 7 * k, cy - 4 * k), 3.2 * k * u)
        pygame.draw.circle(s, feature, P(cx + 7 * k, cy - 4 * k), 3.2 * k * u)
        pygame.draw.arc(s, feature, R(cx - 8 * k, cy - 3 * k, 16 * k, 12 * k),
                        math.pi + 0.3, 2 * math.pi - 0.3, max(2, round(2.2 * k * u)))

    if shape == "star":
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            r = 48 if i % 2 == 0 else 21
            pts.append(P(50 + r * math.cos(a), 54 + r * math.sin(a)))
        poly(color, pts)
        face(50, 54)
    elif shape == "heart":
        pts = []
        for i in range(72):
            t = i / 72 * 2 * math.pi
            x = 16 * math.sin(t) ** 3
            y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
            pts.append(P(50 + x * 2.8, 50 + (y - 2.5) * 2.8))
        poly(color, pts)
        face(50, 44, 1.1)
    elif shape == "smiley":
        circle(color, 50, 50, 46)
        pygame.draw.ellipse(s, feature, R(33, 26, 10, 18))
        pygame.draw.ellipse(s, feature, R(57, 26, 10, 18))
        pygame.draw.arc(s, feature, R(26, 32, 48, 44), math.pi + 0.25, 2 * math.pi - 0.25,
                        round(4 * u))
    elif shape == "flower":
        for i in range(6):
            a = i * math.pi / 3
            circle(color, 50 + 28 * math.cos(a), 50 + 28 * math.sin(a), 19)
        near_yellow = abs(color[0] - 255) + abs(color[1] - 214) + color[2] < 120
        circle((255, 130, 0) if near_yellow else (255, 210, 0), 50, 50, 18)
        face(50, 52, 0.9)
    elif shape == "sun":
        for i in range(12):
            a = i * math.pi / 6
            poly(color, [P(50 + 30 * math.cos(a - 0.2), 50 + 30 * math.sin(a - 0.2)),
                         P(50 + 48 * math.cos(a), 50 + 48 * math.sin(a)),
                         P(50 + 30 * math.cos(a + 0.2), 50 + 30 * math.sin(a + 0.2))])
        circle(color, 50, 50, 31)
        face(50, 52, 1.4)
    elif shape == "fish":
        poly(color, [P(44, 30), P(56, 12), P(66, 32)])
        poly(color, [P(30, 50), P(4, 26), P(12, 50), P(4, 74)])
        ellipse(color, R(22, 26, 64, 48))
        circle(WHITE, 70, 44, 8)
        pygame.draw.circle(s, INK, P(72, 45), 4 * u)
        pygame.draw.arc(s, dark, R(70, 52, 12, 10), math.pi + 0.3, 2 * math.pi - 0.3, ow)
    elif shape == "car":
        poly(color, [P(22, 48), P(32, 24), P(68, 24), P(80, 48)])
        body = R(6, 46, 88, 28)
        pygame.draw.rect(s, color, body, border_radius=round(8 * u))
        pygame.draw.rect(s, dark, body, ow, border_radius=round(8 * u))
        poly((170, 225, 255), [P(31, 46), P(37, 29), P(48, 29), P(48, 46)])
        poly((170, 225, 255), [P(53, 46), P(53, 29), P(64, 29), P(72, 46)])
        circle((255, 230, 90), 89, 56, 4)
        for x in (28, 72):
            pygame.draw.circle(s, (40, 40, 45), P(x, 76), 13 * u)
            pygame.draw.circle(s, (200, 200, 205), P(x, 76), 5 * u)
    elif shape == "train":
        draw_train(s, 0, 15 * u, 0.5 * u, color)
    elif shape == "butterfly":
        for rect in (R(6, 10, 42, 44), R(52, 10, 42, 44), R(14, 48, 34, 36), R(52, 48, 34, 36)):
            ellipse(color, rect)
        spot = lighter(color, 0.55)
        for x, y, r in ((27, 32, 9), (73, 32, 9), (31, 66, 6), (69, 66, 6)):
            circle(spot, x, y, r, outline=False)
        pygame.draw.line(s, INK, P(48, 22), P(38, 6), ow)
        pygame.draw.line(s, INK, P(52, 22), P(62, 6), ow)
        pygame.draw.circle(s, INK, P(38, 6), 3 * u)
        pygame.draw.circle(s, INK, P(62, 6), 3 * u)
        pygame.draw.ellipse(s, INK, R(44, 18, 12, 66))
    elif shape == "rocket":
        pygame.draw.polygon(s, (255, 140, 0), [P(40, 76), P(50, 98), P(60, 76)])
        pygame.draw.polygon(s, (255, 220, 0), [P(44, 76), P(50, 90), P(56, 76)])
        poly(dark, [P(36, 54), P(20, 82), P(38, 76)])
        poly(dark, [P(64, 54), P(80, 82), P(62, 76)])
        ellipse(color, R(33, 4, 34, 80))
        circle((170, 225, 255), 50, 36, 9)
    return pygame.transform.smoothscale(s, (size, size))


def make_icon(size):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(s, (255, 250, 235), s.get_rect(), border_radius=size // 6)
    cx, cy = size / 2, size * 0.62
    band = size * 0.05
    for i, col in enumerate(RAINBOW):
        pygame.draw.circle(s, col, (cx, cy), size * 0.44 - i * band,
                           draw_top_left=True, draw_top_right=True)
    pygame.draw.circle(s, (255, 250, 235), (cx, cy), size * 0.44 - 7 * band,
                       draw_top_left=True, draw_top_right=True)
    train = make_train_sprite(round(size * 0.6))
    s.blit(train, train.get_rect(center=(cx, size * 0.74)))
    return s


# ------------------------------------------------------------------- sound

class Sounds:
    def __init__(self, enabled=True):
        self.ok = False
        self.snd = {}
        if not enabled:
            return
        try:
            import numpy as np
            self.np = np
            pygame.mixer.init(44100, -16, 2, 512, allowedchanges=0)
            pygame.mixer.set_num_channels(24)
            self.rate, _, self.channels = pygame.mixer.get_init()
            self._build()
            self.ok = True
        except Exception as exc:  # no audio device, no numpy... paint quietly
            print(f"Euan Paint: sound disabled ({exc})", file=sys.stderr)

    def _t(self, dur):
        return self.np.arange(int(self.rate * dur)) / self.rate

    def _make(self, wave, vol):
        np = self.np
        peak = np.max(np.abs(wave)) or 1
        data = (np.clip(wave / peak * vol, -1, 1) * 32767).astype(np.int16)
        if self.channels > 1:
            data = np.repeat(data[:, None], self.channels, axis=1)
        return pygame.sndarray.make_sound(np.ascontiguousarray(data))

    def _build(self):
        np = self.np
        tau = 2 * np.pi
        rng = np.random.default_rng(7)

        def noise(n, smooth):
            return np.convolve(rng.standard_normal(n), np.ones(smooth) / smooth, mode="same")

        # Pentatonic xylophone notes, one per colour.
        steps = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24, 26, 28, 31]
        self.notes = []
        for st in steps[:len(PALETTE)]:
            f = 523.25 * 2 ** (st / 12)
            t = self._t(0.45)
            w = np.sin(tau * f * t) + 0.35 * np.sin(2 * tau * f * t) + 0.12 * np.sin(3 * tau * f * t)
            w *= np.exp(-t * 7) * np.minimum(1, t / 0.004)
            self.notes.append(self._make(w, 0.35))

        t = self._t(0.13)
        f = 260 + 1400 * (t / 0.13) ** 1.5
        self.snd["pop"] = self._make(np.sin(tau * np.cumsum(f) / self.rate)
                                     * np.exp(-t * 22) * np.minimum(1, t / 0.003), 0.45)

        t = self._t(0.16)
        self.snd["chuff"] = [self._make(noise(len(t), 10 + 4 * i) * np.exp(-t * 28), 0.3)
                             for i in range(3)]

        t = self._t(0.8)
        vib = 1 + 0.008 * np.sin(tau * 5.5 * t)
        w = sum(np.sin(tau * np.cumsum(f0 * vib) / self.rate) for f0 in (587, 740, 880))
        w = w + 0.4 * noise(len(t), 3)
        env = np.minimum(1, t / 0.04) * np.clip((0.8 - t) / 0.2, 0, 1)
        self.snd["whistle"] = self._make(w * env, 0.3)

        t = self._t(0.6)
        self.snd["whoosh"] = self._make(noise(len(t), 6) * np.sin(np.pi * t / 0.6) ** 2, 0.4)

        t = self._t(0.06)
        self.snd["click"] = self._make(np.sin(tau * 1300 * t) * np.exp(-t * 70), 0.3)

        def semi(st, base=523.25):
            return base * 2 ** (st / 12)

        def bell(f, dur=0.5, decay=8.0):
            t = self._t(dur)
            return ((np.sin(tau * f * t) + 0.3 * np.sin(2 * tau * f * t))
                    * np.exp(-t * decay) * np.minimum(1, t / 0.003))

        def sweep(f0, f1, dur, curve=1.0):
            t = self._t(dur)
            f = f0 + (f1 - f0) * (t / dur) ** curve
            return np.sin(tau * np.cumsum(f) / self.rate), t

        def seq(parts, total):
            out = np.zeros(int(self.rate * total))
            for start, w in parts:
                i = int(start * self.rate)
                n = min(len(w), len(out) - i)
                out[i:i + n] += w[:n]
            return out

        # Glitter: little high bell tinkles.
        self.snd["tinkle"] = [self._make(seq([(0, bell(semi(st, 1046.5), 0.4, 14)),
                                              (0.05, bell(semi(st + 7, 1046.5), 0.35, 16))], 0.45),
                                         0.18)
                              for st in (0, 2, 4, 7, 9, 12)]

        # Paint bucket: a downward "bloop" with a bubbly splash.
        w, t = sweep(900, 170, 0.32, 0.6)
        self.snd["sploosh"] = self._make(w * np.exp(-t * 9) + 0.25 * noise(len(t), 4)
                                         * np.exp(-t * 20), 0.45)

        # Undo: a quick two-step "bwoop" down.
        w1, t1 = sweep(880, 620, 0.09)
        w2, t2 = sweep(620, 380, 0.12)
        self.snd["undo"] = self._make(seq([(0, w1 * np.sin(np.pi * t1 / 0.09)),
                                           (0.1, w2 * np.sin(np.pi * t2 / 0.12))], 0.24), 0.35)

        # A noise for every stamp.
        stamp = {}
        stamp["star"] = seq([(i * 0.07, bell(semi(st, 1046.5), 0.5, 9))
                             for i, st in enumerate((0, 4, 7, 12))], 0.8)
        thump, t = sweep(120, 55, 0.18)
        thump *= np.exp(-t * 16)
        stamp["heart"] = seq([(0, thump), (0.2, thump * 0.8)], 0.42)
        chirps = []
        for i, base in enumerate((950, 900, 850, 800)):
            w, t = sweep(base, base * 1.35, 0.07)
            chirps.append((i * 0.09, w * np.sin(np.pi * t / 0.07)))
        stamp["smiley"] = seq(chirps, 0.4)
        stamp["flower"] = seq([(i * 0.05, bell(semi(st), 0.6, 6))
                               for i, st in enumerate((24, 21, 19, 16, 14, 12))], 0.9)
        t = self._t(0.8)
        stamp["sun"] = (sum(np.sin(tau * semi(st) * t) for st in (0, 4, 7, 12))
                        * np.minimum(1, t / 0.15) * np.exp(-np.maximum(0, t - 0.15) * 5))
        bubbles = []
        for i in range(3):
            w, t = sweep(300 + 150 * i, 1300 + 200 * i, 0.06, 2)
            bubbles.append((i * 0.09, w * np.sin(np.pi * t / 0.06)))
        stamp["fish"] = seq(bubbles, 0.3)
        t = self._t(0.13)
        beep = sum(np.sin(tau * 520 * k * t) / k for k in (1, 3, 5)) * np.minimum(1, t / 0.01) \
            * np.clip((0.13 - t) / 0.02, 0, 1)
        stamp["car"] = seq([(0, beep), (0.19, beep)], 0.34)
        t = self._t(0.45)
        stamp["train"] = (sum(np.sin(tau * f0 * t) for f0 in (587, 740, 880))
                          * np.minimum(1, t / 0.03) * np.clip((0.45 - t) / 0.12, 0, 1))
        t = self._t(0.4)
        stamp["butterfly"] = (np.sin(tau * 1500 * t) * (0.5 + 0.5 * np.sin(tau * 22 * t))
                              * np.sin(np.pi * t / 0.4))
        w, t = sweep(150, 1400, 0.7, 1.5)
        stamp["rocket"] = (w + 0.6 * noise(len(t), 3)) * np.minimum(1, t / 0.1) \
            * np.clip((0.7 - t) / 0.25, 0, 1)
        for name, wave in stamp.items():
            self.snd["stamp_" + name] = self._make(wave, 0.4)

    def play(self, name):
        if not self.ok:
            return
        snd = self.snd[name]
        if isinstance(snd, list):
            snd = random.choice(snd)
        snd.play()

    def note(self, i):
        if self.ok:
            self.notes[i % len(self.notes)].play()


# --------------------------------------------------------------------- app

class App:
    def __init__(self, screen, sounds, voice=True, windowed=False):
        self.screen = screen
        self.W, self.H = screen.get_size()
        self.sounds = sounds
        self.voice = voice and shutil.which("spd-say") is not None
        self.windowed = windowed
        self.layout()

        self.canvas = pygame.Surface(self.canvas_rect.size).convert()
        self.canvas.fill(WHITE)
        self.dirty = False

        self.tool = "brush"
        self.color_i = 0
        self.size_i = 1
        self.stamp_i = 0

        self.drawing = False
        self.mouse = self.prev = self.canvas_rect.center
        self.last_stamp_pos = None
        self.tdir = (1.0, 0.0)
        self.chuff_travel = 0.0
        self.smoke_travel = 0.0

        self.anims = []       # [surface, canvas-local centre, start time]
        self.confetti = []    # [x, y, vx, vy, life, max_life, colour, radius]
        self.smoke = []       # [x, y, vx, vy, life, max_life, radius]
        self.twinkles = []    # [x, y, life, max_life, radius, colour, angle]
        self.fills = []       # [surface, canvas-local rect, canvas-local origin, start, duration]
        self.clear_fx = None  # (old canvas, start time)
        self.undo_fx = None   # (canvas before undo, start time)
        self.undo_stack = []  # canvas snapshots, oldest first
        self.help_until = -1.0
        self.glitter_travel = 0.0
        self.track = None     # railway being drawn: dict(pts, heads, gauge)
        self.railways = []    # finished railways: dict(pts, heads, gauge, cum)
        self.trains = []      # trains running along railways
        self.rainbow = None   # rainbow being drawn: dict(pts, stripe)
        self.rainbows = []    # finished rainbows: dict(pts, stripe, cum)
        self.sparkle_runs = []  # bursts of sparkles racing along rainbows
        self.next_sparkle_at = 0.0
        self.sparkle_target = None
        self.train_next = None  # newly drawn railway the train should visit next
        self.sprite_cache = {}
        self.tunnel_cache = {}

        self.pressed = set()
        self.shake = []          # recent (time, dx, dy) mouse moves
        self.cursor_boost = 0.0  # 0..1, how big the "here I am" pointer is
        self.exit_hold = 0.0
        self.running = True

        self.now = 0.0
        self.color_changed_at = -10.0
        self.speak_at = None
        self.last_wheel = self.last_pop = self.last_key_stamp = -10.0
        self.last_whistle = -10.0

        self.stamp_cache = {}
        self.puff_cache = {}
        self.puff = self._make_puff()
        self.font = pygame.font.Font(None, max(26, self.H // 30))
        self.splash = self._make_splash()

    # ----------------------------------------------------------- layout
    def layout(self):
        W, H = self.W, self.H
        self.TOOL_W = max(96, min(150, W // 13))
        self.BAR_H = max(90, min(130, H // 9))
        avail = H - self.BAR_H
        self.canvas_rect = pygame.Rect(self.TOOL_W, 0, W - 2 * self.TOOL_W, avail)

        def column(n, x0):
            b = int(min(self.TOOL_W - 20, avail / n - 12))
            gap = (avail - b * n) / (n + 1)
            x = x0 + (self.TOOL_W - b) // 2
            return b, [pygame.Rect(x, round(gap * (i + 1) + b * i), b, b) for i in range(n)]

        self.tool_size, rects = column(len(TOOLS), 0)
        self.tool_buttons = list(zip(TOOLS, rects))
        self.stamp_size, rects = column(len(STAMPS), W - self.TOOL_W)
        self.stamp_buttons = list(zip(range(len(STAMPS)), rects))

        spacing = W / len(PALETTE)
        cy = H - self.BAR_H / 2
        self.swatch_r = min(self.BAR_H * 0.3, spacing * 0.36)
        self.swatches = [(spacing * (i + 0.5), cy) for i in range(len(PALETTE))]
        self.swatch_spacing = spacing

    @property
    def color(self):
        return PALETTE[self.color_i][1]

    @property
    def size(self):
        return SIZES[self.size_i]

    def grab(self):
        if self.windowed:
            return
        pygame.event.set_grab(True)
        try:
            pygame.event.set_keyboard_grab(True)
        except (AttributeError, pygame.error):
            pass

    # ----------------------------------------------------------- events
    def handle(self, e):
        t = e.type
        if t == pygame.QUIT:
            # Alt+F4 and friends: ignored in fullscreen, only a grown-up exits.
            if self.windowed:
                self.running = False
        elif t == pygame.WINDOWFOCUSLOST:
            self.pressed.clear()
            self.end_stroke()
        elif t == pygame.WINDOWFOCUSGAINED:
            self.grab()
        elif t == pygame.KEYDOWN:
            self.pressed.add(e.key)
            self.on_key(e.key)
        elif t == pygame.KEYUP:
            self.pressed.discard(e.key)
        elif t == pygame.MOUSEWHEEL:
            v = e.y or -e.x
            if v and self.now - self.last_wheel > 0.05:
                self.last_wheel = self.now
                self.set_color((self.color_i + (1 if v < 0 else -1)) % len(PALETTE))
        elif t == pygame.MOUSEBUTTONDOWN:
            self.mouse = e.pos
            if e.button in (1, 2):
                self.press(e.pos)
            elif e.button == 3:
                if self.tool == "stamp":
                    self.stamp_i = (self.stamp_i + 1) % len(STAMPS)
                self.tool = "stamp"
                self.sounds.play("click")
        elif t == pygame.MOUSEBUTTONUP:
            if e.button in (1, 2):
                self.end_stroke()
        elif t == pygame.MOUSEMOTION:
            self.shake.append((self.now, e.pos[0] - self.mouse[0], e.pos[1] - self.mouse[1]))
            self.mouse = e.pos
            self.motion(e.pos)

    def on_key(self, key):
        if key == pygame.K_ESCAPE:
            self.help_until = self.now + 6
            return
        if key == pygame.K_z and self.pressed & CTRL_KEYS:
            self.undo()
            return
        if key in MODIFIER_KEYS or self.pressed & CTRL_KEYS:
            return
        if self.now - self.last_key_stamp < 0.07:
            return
        self.last_key_stamp = self.now
        size = random.randint(80, 150)
        area = self.canvas_rect.inflate(-size, -size)
        pos = (random.randint(area.left, area.right), random.randint(area.top, area.bottom))
        color = random.choice(PALETTE[:-1])[1]
        self.push_undo()
        self.place_stamp(pos, random.choice(STAMPS), color, size, rot=random.uniform(-15, 15))

    def press(self, pos):
        if not self.canvas_rect.collidepoint(pos):
            self.click_ui(pos)
            return
        self.drawing = True
        self.prev = pos
        if self.tool != "bucket":
            self.push_undo()
        if self.tool in ("brush", "eraser"):
            self.paint_segment(pos, pos)
        elif self.tool == "glitter":
            self.glitter_segment(pos, pos)
            self.sounds.play("tinkle")
        elif self.tool == "railway":
            self.track = dict(pts=[self.to_canvas(pos)], heads=[self.tdir],
                              gauge=self.size["gauge"])
        elif self.tool == "bucket":
            self.drawing = False
            self.flood_fill(pos)
        elif self.tool == "rainbow":
            self.rainbow = dict(pts=[], stripe=self.size["stripe"])
            self.sounds.play("tinkle")
        elif self.tool == "stamp":
            self.place_stamp(pos, STAMPS[self.stamp_i], self.color, self.size["stamp"])

    def motion(self, pos):
        a, self.prev = self.prev, pos
        if self.tool == "rainbow":
            self.train_segment(a, pos, draw=self.drawing)
        elif self.tool == "railway":
            if self.drawing and self.track:
                self.rail_segment(pos)
            else:
                self.train_segment(a, pos, draw=False)
        if not self.drawing:
            return
        if self.tool in ("brush", "eraser"):
            self.paint_segment(a, pos)
        elif self.tool == "glitter":
            self.glitter_segment(a, pos)
        elif self.tool == "stamp" and self.canvas_rect.collidepoint(pos):
            lx, ly = self.last_stamp_pos or (-9999, -9999)
            if math.hypot(pos[0] - lx, pos[1] - ly) > self.size["stamp"] * 0.9:
                self.place_stamp(pos, STAMPS[self.stamp_i], self.color, self.size["stamp"])

    def click_ui(self, pos):
        for name, rect in self.tool_buttons:
            if rect.collidepoint(pos):
                if name == "clear":
                    self.clear()
                elif name == "undo":
                    self.undo()
                elif name == "size":
                    self.size_i = (self.size_i + 1) % len(SIZES)
                    self.sounds.play("click")
                else:
                    self.tool = name
                    self.sounds.play({"rainbow": "tinkle", "glitter": "tinkle",
                                      "bucket": "sploosh"}.get(name, "click"))
                return
        for i, rect in self.stamp_buttons:
            if rect.collidepoint(pos):
                self.tool = "stamp"
                self.stamp_i = i
                self.sounds.play("stamp_" + STAMPS[i])
                return
        if pos[1] > self.H - self.BAR_H:
            i = int(pos[0] // self.swatch_spacing)
            if 0 <= i < len(PALETTE):
                self.set_color(i)

    def set_color(self, i):
        self.color_i = i
        self.color_changed_at = self.now
        if self.tool == "eraser":
            self.tool = "brush"
        self.sounds.note(i)
        self.speak_at = self.now + 0.5

    # ---------------------------------------------------------- painting
    def to_canvas(self, p):
        return (p[0] - self.canvas_rect.x, p[1] - self.canvas_rect.y)

    def paint_segment(self, a, b):
        if self.tool == "eraser":
            radius, color = self.size["eraser"], WHITE
        else:
            radius, color = self.size["brush"], self.color
        a, b = self.to_canvas(a), self.to_canvas(b)
        dist = math.hypot(b[0] - a[0], b[1] - a[1])
        steps = max(1, int(dist / max(1.0, radius * 0.35)))
        for i in range(steps + 1):
            t = i / steps
            pygame.draw.circle(self.canvas, color,
                               (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), radius)
        self.dirty = True

    def train_segment(self, a, b, draw):
        """Move the train from a to b, laying rainbow track behind it when drawing."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        dist = math.hypot(dx, dy)
        if dist < 0.01:
            return
        ux, uy = dx / dist, dy / dist
        tx, ty = self.tdir
        sw = self.size["stripe"]
        ox, oy = self.canvas_rect.topleft
        n = max(1, int(dist / 2))
        for i in range(1, n + 1):
            # Ease the heading so the stripes bend smoothly instead of kinking.
            tx, ty = tx * 0.86 + ux * 0.14, ty * 0.86 + uy * 0.14
            norm = math.hypot(tx, ty) or 1
            tx, ty = tx / norm, ty / norm
            if draw:
                px = a[0] + dx * i / n - ox
                py = a[1] + dy * i / n - oy
                rb = self.rainbow
                if rb is not None and (not rb["pts"] or math.hypot(px - rb["pts"][-1][0],
                                                                  py - rb["pts"][-1][1]) >= 6):
                    rb["pts"].append((px, py))
                for k, col in enumerate(RAINBOW):
                    off = (k - 3) * sw
                    pygame.draw.circle(self.canvas, col, (px - ty * off, py + tx * off), sw * 0.5 + 1)
        self.tdir = (tx, ty)
        if not draw:
            return
        self.dirty = True
        self.chuff_travel += dist
        if self.chuff_travel > 90:
            self.chuff_travel = 0
            self.sounds.play("tinkle")
        # The star leaves a trail of twinkles over the rainbow behind it.
        self.smoke_travel += dist
        while self.smoke_travel > 12:
            self.smoke_travel -= 12
            off = random.uniform(-3.5, 3.5) * sw
            back = random.uniform(15, 40)
            self.twinkles.append([b[0] - tx * back - ty * off, b[1] - ty * back + tx * off, 0.6, 0.6,
                                  random.uniform(6, 12), random.choice((WHITE, GOLD, (255, 240, 170))),
                                  random.uniform(0, math.pi / 4)])

    def stamp_surface(self, shape, color, size):
        key = (shape, color, size)
        surf = self.stamp_cache.get(key)
        if surf is None:
            if len(self.stamp_cache) > 400:
                self.stamp_cache.clear()
            surf = self.stamp_cache[key] = render_stamp(shape, color, size)
        return surf

    def place_stamp(self, pos, shape, color, size, rot=0.0):
        surf = self.stamp_surface(shape, color, size)
        if rot:
            surf = pygame.transform.rotozoom(surf, rot, 1)
        self.anims.append([surf, self.to_canvas(pos), self.now])
        self.last_stamp_pos = pos
        self.dirty = True
        for _ in range(16):
            a = random.uniform(0, 2 * math.pi)
            sp = random.uniform(150, 420)
            col = color if random.random() < 0.4 else random.choice(RAINBOW)
            self.confetti.append([pos[0], pos[1], math.cos(a) * sp, math.sin(a) * sp - 150,
                                  0.7, 0.7, col, random.uniform(4, 8)])
        if self.now - self.last_pop > 0.05:
            self.last_pop = self.now
            self.sounds.play("stamp_" + shape)

    def glitter_segment(self, a, b):
        """Scatter sparkles and glitter dots along the stroke."""
        spread = self.size["brush"] * 2 + 10
        if self.color == WHITE:
            tints = [(225, 225, 235), (200, 205, 220), GOLD]
        else:
            tints = [self.color, lighter(self.color, 0.45), darker(self.color, 0.8), GOLD]
        dist = math.hypot(b[0] - a[0], b[1] - a[1])
        steps = max(1, int(dist / 7))
        for i in range(steps + 1):
            t = i / steps
            px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            for _ in range(3):
                ang = random.uniform(0, 2 * math.pi)
                rad = spread * math.sqrt(random.random())
                cx = px + math.cos(ang) * rad - self.canvas_rect.x
                cy = py + math.sin(ang) * rad - self.canvas_rect.y
                col = random.choice(tints)
                if random.random() < 0.35:
                    draw_sparkle(self.canvas, col, (cx, cy), random.uniform(4, 9),
                                 random.uniform(0, math.pi / 4))
                else:
                    pygame.draw.circle(self.canvas, col, (cx, cy), random.uniform(1.5, 3.5))
            if random.random() < 0.3:
                ang = random.uniform(0, 2 * math.pi)
                rad = spread * 1.2 * random.random()
                self.twinkles.append([px + math.cos(ang) * rad, py + math.sin(ang) * rad,
                                      0.6, 0.6, random.uniform(10, 18),
                                      random.choice((WHITE, GOLD, lighter(self.color, 0.6))),
                                      random.uniform(0, math.pi / 4)])
        self.dirty = True
        self.glitter_travel += dist
        if self.glitter_travel > 70:
            self.glitter_travel = 0
            self.sounds.play("tinkle")

    def flood_fill(self, pos):
        """Fill the area under pos with the current colour, revealed as a growing ripple."""
        try:
            import numpy as np
        except ImportError:
            return
        self.commit_anims()
        self.commit_fills()
        x, y = (int(v) for v in self.to_canvas(pos))
        rgb = pygame.surfarray.array3d(self.canvas).astype(np.int16).transpose(1, 0, 2)
        target = rgb[y, x].copy()
        if np.abs(target - np.array(self.color)).sum() < 30:
            self.sounds.play("click")
            return
        self.push_undo()
        # Tolerance soaks up the soft edges of stamps and sparkles.
        free = np.abs(rgb - target).sum(axis=2) <= 90
        h, w = free.shape
        filled = np.zeros_like(free)
        stack = [(x, y)]
        while stack:
            sx, sy = stack.pop()
            row = free[sy]
            if not row[sx]:
                continue
            blocked = np.flatnonzero(~row[:sx])
            left = blocked[-1] + 1 if blocked.size else 0
            blocked = np.flatnonzero(~row[sx:])
            right = sx + blocked[0] if blocked.size else w
            filled[sy, left:right] = True
            row[left:right] = False
            for ny in (sy - 1, sy + 1):
                if 0 <= ny < h:
                    seg = free[ny, left:right].astype(np.int8)
                    starts = np.flatnonzero(np.diff(np.concatenate(([0], seg))) == 1)
                    stack.extend((left + s, ny) for s in starts)
        # Grow one pixel so the fill tucks under anti-aliased outlines.
        grown = filled.copy()
        grown[1:] |= filled[:-1]
        grown[:-1] |= filled[1:]
        grown[:, 1:] |= filled[:, :-1]
        grown[:, :-1] |= filled[:, 1:]
        ys, xs = np.nonzero(grown)
        box = pygame.Rect(xs.min(), ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1)
        mask = grown[box.top:box.bottom, box.left:box.right]
        surf = pygame.Surface(box.size, pygame.SRCALPHA)
        surf.fill(self.color)
        alpha = pygame.surfarray.pixels_alpha(surf)
        alpha[:] = (mask.T * 255).astype(np.uint8)
        del alpha
        reach = max(math.hypot(cx - x, cy - y) for cx, cy in
                    (box.topleft, box.topright, box.bottomleft, box.bottomright))
        self.fills.append([surf, box, (x, y), self.now, min(0.6, max(0.25, reach / 1800))])
        self.dirty = True
        self.sounds.play("sploosh")

    def commit_anims(self):
        for surf, (x, y), _ in self.anims:
            self.canvas.blit(surf, surf.get_rect(center=(round(x), round(y))))
        self.anims.clear()

    def commit_fills(self):
        for surf, box, _, _, _ in self.fills:
            self.canvas.blit(surf, box)
        self.fills.clear()

    def end_stroke(self):
        self.drawing = False
        rb, self.rainbow = self.rainbow, None
        if rb and len(rb["pts"]) > 1:
            cum = [0.0]
            for (x0, y0), (x1, y1) in zip(rb["pts"], rb["pts"][1:]):
                cum.append(cum[-1] + math.hypot(x1 - x0, y1 - y0))
            if cum[-1] >= 80:
                rb["cum"] = cum
                self.rainbows.append(rb)
                self.next_sparkle_at = self.now + 1.0
                self.sparkle_target = rb
        track, self.track = self.track, None
        if not track or len(track["pts"]) < 2:
            return
        # Redraw the whole line so rails sit cleanly on top of every sleeper.
        draw_track(self.canvas, track["pts"], track["heads"], track["gauge"])
        cum = [0.0]
        for (x0, y0), (x1, y1) in zip(track["pts"], track["pts"][1:]):
            cum.append(cum[-1] + math.hypot(x1 - x0, y1 - y0))
        if cum[-1] < track["gauge"] * 12:
            return
        self.add_tunnel_approaches(track, cum)
        cum = track["cum"]
        pts, heads, g, L = track["pts"], track["heads"], track["gauge"], cum[-1]
        track["tunnels"] = [self.build_tunnel(track, 0), self.build_tunnel(track, -1)]
        # Paint the tunnels into the picture: dark inside, the track running into
        # it, then the hill and arch on top.
        for _, inside, pos in track["tunnels"]:
            self.canvas.blit(inside, pos)
        reach = g * TUNNEL_SIZE
        head = bisect.bisect_right(cum, reach) + 1
        phase = track["phase"]
        draw_track(self.canvas, pts[:head], heads[:head], g, phase=phase)
        draw_track(self.canvas, pts, heads, g, max(1, bisect.bisect_left(cum, L - reach)), phase=phase)
        for front, _, pos in track["tunnels"]:
            self.canvas.blit(front, pos)
        self.railways.append(track)
        if self.trains:
            self.train_next = track
        else:
            self.launch_train(track)

    def add_tunnel_approaches(self, track, cum):
        """Curve each end of the track round so it runs level into an upright tunnel."""
        pts, g = track["pts"], track["gauge"]
        L = cum[-1]

        def outward(from_end):
            # Direction leaving the track at one end, measured over a few gauges.
            if from_end:
                j = max(0, bisect.bisect_right(cum, L - 3 * g) - 1)
                a, b = pts[j], pts[-1]
            else:
                j = min(len(pts) - 1, bisect.bisect_left(cum, 3 * g))
                a, b = pts[j], pts[0]
            n = math.hypot(b[0] - a[0], b[1] - a[1]) or 1
            return (b[0] - a[0]) / n, (b[1] - a[1]) / n

        def approach(end, u):
            side = 1 if u[0] >= 0 else -1
            # Keep the whole hill on the page vertically.
            h = g * TUNNEL_SIZE * 0.8
            gy = end[1] + u[1] * 2.5 * g
            gy = max(h * TUNNEL_ANCHOR[1] + 2, min(self.canvas_rect.h - h * (1 - TUNNEL_ANCHOR[1]) - 2, gy))
            goal = (end[0] + side * 5 * g, gy)
            c = 2.2 * g
            ctrl = [end, (end[0] + u[0] * c, end[1] + u[1] * c), (goal[0] - side * c, goal[1]), goal]
            out, last, acc = [], end, 0.0
            for i in range(1, 201):
                t = i / 200
                m = 1 - t
                x = m ** 3 * ctrl[0][0] + 3 * m * m * t * ctrl[1][0] + 3 * m * t * t * ctrl[2][0] + t ** 3 * ctrl[3][0]
                y = m ** 3 * ctrl[0][1] + 3 * m * m * t * ctrl[1][1] + 3 * m * t * t * ctrl[2][1] + t ** 3 * ctrl[3][1]
                acc += math.hypot(x - last[0], y - last[1])
                last = (x, y)
                if acc >= 4 or i == 200:
                    out.append((x, y))
                    acc = 0.0
            return out, side

        head, side0 = approach(pts[0], outward(False))
        tail, side1 = approach(pts[-1], outward(True))
        new = head[::-1] + pts + tail
        heads = []
        for i in range(len(new)):
            if len(head) <= i < len(head) + len(pts):
                heads.append(track["heads"][i - len(head)])
                continue
            a, b = new[max(0, i - 1)], new[min(len(new) - 1, i + 1)]
            n = math.hypot(b[0] - a[0], b[1] - a[1]) or 1
            heads.append(((b[0] - a[0]) / n, (b[1] - a[1]) / n))
        cum = [0.0]
        for (x0, y0), (x1, y1) in zip(new, new[1:]):
            cum.append(cum[-1] + math.hypot(x1 - x0, y1 - y0))
        track.update(pts=new, heads=heads, cum=cum, sides=(side0, side1), phase=len(head) % 4)

    def build_tunnel(self, rail, end_i):
        """Upright tunnel at one end of a railway, its mouth facing the track.

        Returns (front, interior, canvas top-left)."""
        side = rail["sides"][end_i]
        width = round(rail["gauge"] * TUNNEL_SIZE)
        key = (width, side)
        if key not in self.tunnel_cache:
            front, inside = make_tunnel_sprites(width)
            if side < 0:
                front = pygame.transform.flip(front, True, False)
                inside = pygame.transform.flip(inside, True, False)
            self.tunnel_cache[key] = (front, inside)
        front, inside = self.tunnel_cache[key]
        w, h = front.get_size()
        ax = TUNNEL_ANCHOR[0] if side > 0 else 1 - TUNNEL_ANCHOR[0]
        x, y = rail["pts"][end_i]
        return front, inside, (round(x - w * ax), round(y - h * TUNNEL_ANCHOR[1]))

    def rail_segment(self, pos):
        """Extend the railway being drawn towards pos, a sample every 4 px."""
        tr = self.track
        bx, by = self.to_canvas(pos)
        lx, ly = tr["pts"][-1]
        dist = math.hypot(bx - lx, by - ly)
        n = int(dist // 4)
        if n == 0:
            return
        ux, uy = (bx - lx) / dist, (by - ly) / dist
        tx, ty = self.tdir
        if len(tr["pts"]) == 1:
            tx, ty = ux, uy
            tr["heads"][0] = (ux, uy)
        start = len(tr["pts"])
        for i in range(1, n + 1):
            tx, ty = tx * 0.8 + ux * 0.2, ty * 0.8 + uy * 0.2
            norm = math.hypot(tx, ty) or 1
            tx, ty = tx / norm, ty / norm
            tr["pts"].append((lx + ux * 4 * i, ly + uy * 4 * i))
            tr["heads"].append((tx, ty))
        self.tdir = (tx, ty)
        draw_track(self.canvas, tr["pts"], tr["heads"], tr["gauge"], start)
        self.dirty = True
        self.chuff_travel += dist
        if self.chuff_travel > 70:
            self.chuff_travel = 0
            self.sounds.play("click")

    def launch_train(self, rail):
        """Start the one and only train, coming out of a tunnel on rail."""
        cars = random.sample(RAINBOW[1:], k=random.randint(2, 4))
        self.trains = [dict(cars=cars, chuff=0.0, puff=0.0, wait=0.0)]
        self.put_train_on(self.trains[0], rail)

    def put_train_on(self, train, rail):
        train.update(rail=rail, d=0.0, dir=random.choice((1, -1)),
                     width=round(rail["gauge"] * 5.5), speed=rail["gauge"] * 9)
        if self.now - self.last_whistle > 1.5:
            self.last_whistle = self.now
            self.sounds.play("whistle")

    def next_railway(self, rail):
        """Where the train comes out after going into a tunnel: a new track first, else the next one."""
        nxt, self.train_next = self.train_next, None
        if any(nxt is r for r in self.railways):
            return nxt
        i = next((i for i, r in enumerate(self.railways) if r is rail), -1)
        return self.railways[(i + 1) % len(self.railways)]

    def rail_point(self, rail, s):
        """Canvas position and travel heading at distance s along a railway."""
        cum, pts = rail["cum"], rail["pts"]
        s = max(0.0, min(cum[-1], s))
        i = max(1, min(len(cum) - 1, bisect.bisect_left(cum, s)))
        seg = cum[i] - cum[i - 1] or 1
        t = (s - cum[i - 1]) / seg
        (x0, y0), (x1, y1) = pts[i - 1], pts[i]
        return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t

    def train_cars(self, train):
        """Each vehicle of a train as (sprite kind, colour, position, heading), engine first."""
        rail, L = train["rail"], train["rail"]["cum"][-1]
        gap = train["width"] * 0.92
        out = []
        for i, col in enumerate([None] + train["cars"]):
            along = train["d"] - i * gap
            if not 0 <= along <= L:
                continue
            s = along if train["dir"] > 0 else L - along
            x, y = self.rail_point(rail, s)
            ax, ay = self.rail_point(rail, s - 6 * train["dir"])
            bx, by = self.rail_point(rail, s + 6 * train["dir"])
            norm = math.hypot(bx - ax, by - ay) or 1
            out.append(("engine" if col is None else "car", col, (x, y),
                        ((bx - ax) / norm, (by - ay) / norm)))
        return out

    def sprite(self, kind, color, width, left):
        key = (kind, color, width, left)
        img = self.sprite_cache.get(key)
        if img is None:
            if kind == "engine":
                img = make_train_sprite(width)
            else:
                img = make_carriage_sprite(width, color)
            if left:
                img = pygame.transform.flip(img, True, False)
            self.sprite_cache[key] = img
        return img

    def update_trains(self, dt):
        ox, oy = self.canvas_rect.topleft
        for tr in self.trains:
            if tr["wait"] > 0:
                # Underground between tunnels.
                tr["wait"] -= dt
                if tr["wait"] <= 0:
                    self.put_train_on(tr, self.next_railway(tr["rail"]))
                continue
            if tr["d"] - len(tr["cars"]) * tr["width"] > tr["rail"]["cum"][-1] + 10:
                tr["wait"] = 1.0
                continue
            tr["d"] += tr["speed"] * dt
            tr["chuff"] += dt
            tr["puff"] += dt
            if tr["chuff"] > 0.4:
                tr["chuff"] = 0
                self.sounds.play("chuff")
            if tr["puff"] > 0.14:
                tr["puff"] = 0
                cars = self.train_cars(tr)
                if cars and cars[0][0] == "engine":
                    _, _, (x, y), (tx, ty) = cars[0]
                    w = tr["width"]
                    up = (ty, -tx) if tx >= 0 else (-ty, tx)
                    self.smoke.append([ox + x + tx * 0.24 * w + up[0] * 0.27 * w,
                                       oy + y + ty * 0.24 * w + up[1] * 0.27 * w,
                                       up[0] * 40 - tx * 25, up[1] * 40 - ty * 25,
                                       1.0, 1.0, w * 0.1])
        if self.railways and not self.trains:
            self.launch_train(random.choice(self.railways))

    def update_sparkle_runs(self, dt):
        """Every so often a burst of sparkles races along one of the rainbows."""
        if self.rainbows and self.now >= self.next_sparkle_at:
            rb = self.sparkle_target if self.sparkle_target in self.rainbows else random.choice(self.rainbows)
            self.sparkle_target = None
            self.sparkle_runs.append(dict(rb=rb, d=0.0, dir=random.choice((1, -1)),
                                          speed=random.uniform(450, 650), spin=0.0))
            self.next_sparkle_at = self.now + random.uniform(3, 6)
            self.sounds.play("tinkle")
        ox, oy = self.canvas_rect.topleft
        for run in self.sparkle_runs:
            rb, L = run["rb"], run["rb"]["cum"][-1]
            run["d"] += run["speed"] * dt
            run["spin"] += 6 * dt
            s = run["d"] if run["dir"] > 0 else L - run["d"]
            x, y = self.rail_point(rb, s)
            ax, ay = self.rail_point(rb, s - 4)
            bx, by = self.rail_point(rb, s + 4)
            n = math.hypot(bx - ax, by - ay) or 1
            nx, ny = -(by - ay) / n, (bx - ax) / n
            band = rb["stripe"] * 3.5
            for _ in range(4):
                off = random.uniform(-band, band)
                self.twinkles.append([ox + x + nx * off, oy + y + ny * off, 0.7, 0.7,
                                      random.uniform(5, 11) * (1 + rb["stripe"] / 10),
                                      random.choice((WHITE, WHITE, GOLD, (255, 240, 170))),
                                      random.uniform(0, math.pi / 4)])
            run["head"] = (ox + x, oy + y)
        self.sparkle_runs = [r for r in self.sparkle_runs if r["d"] < r["rb"]["cum"][-1]]

    def draw_sparkle_heads(self):
        for run in self.sparkle_runs:
            if "head" not in run:
                continue
            r = 10 + run["rb"]["stripe"] * 2.2
            draw_sparkle(self.screen, GOLD, run["head"], r * 1.25, run["spin"])
            draw_sparkle(self.screen, WHITE, run["head"], r, run["spin"])

    def draw_trains(self):
        ox, oy = self.canvas_rect.topleft
        for tr in self.trains:
            # Draw back to front so the engine sits on top of its carriages.
            if tr["wait"] > 0:
                continue
            for kind, col, (x, y), (tx, ty) in reversed(self.train_cars(tr)):
                deg = -math.degrees(math.atan2(ty, tx))
                img = self.sprite(kind, col, tr["width"], tx < 0)
                img = pygame.transform.rotate(img, deg + (180 if tx < 0 else 0))
                self.screen.blit(img, img.get_rect(center=(ox + x, oy + y)))
        # Tunnels go on top so trains vanish inside them.
        for rail in self.railways:
            for front, _, (x, y) in rail["tunnels"]:
                self.screen.blit(front, (ox + x, oy + y))

    def push_undo(self):
        """Remember the page as it looks now, including stamps and fills still animating."""
        snap = self.canvas.copy()
        for surf, (x, y), _ in self.anims:
            snap.blit(surf, surf.get_rect(center=(round(x), round(y))))
        for surf, box, _, _, _ in self.fills:
            snap.blit(surf, box)
        self.undo_stack.append((snap, list(self.railways), list(self.rainbows)))
        del self.undo_stack[:-UNDO_STEPS]

    def undo(self):
        if not self.undo_stack:
            self.sounds.play("click")
            return
        self.drawing = False
        self.anims.clear()
        self.fills.clear()
        self.clear_fx = None
        self.undo_fx = (self.canvas, self.now)
        self.canvas, self.railways, self.rainbows = self.undo_stack.pop()
        self.rainbow = None
        self.sparkle_runs = [r for r in self.sparkle_runs if any(r["rb"] is b for b in self.rainbows)]
        self.track = None
        self.trains = [tr for tr in self.trains if any(tr["rail"] is r for r in self.railways)]
        self.dirty = True
        self.sounds.play("undo")

    def clear(self):
        self.commit_anims()
        self.commit_fills()
        self.push_undo()
        self.autosave()
        self.clear_fx = (self.canvas.copy(), self.now)
        self.canvas.fill(WHITE)
        self.railways = []
        self.trains = []
        self.rainbows = []
        self.sparkle_runs = []
        self.dirty = False
        self.sounds.play("whoosh")

    def autosave(self):
        if not self.dirty:
            return
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)
            path = SAVE_DIR / time.strftime("euan-%Y-%m-%d-%H%M%S.png")
            pygame.image.save(self.canvas, str(path))
        except (OSError, pygame.error) as exc:
            print(f"Euan Paint: could not save picture ({exc})", file=sys.stderr)

    # ------------------------------------------------------------ update
    def update(self, dt):
        still = []
        for anim in self.anims:
            if self.now - anim[2] >= 0.3:
                surf, (x, y), _ = anim
                self.canvas.blit(surf, surf.get_rect(center=(round(x), round(y))))
            else:
                still.append(anim)
        self.anims = still
        if self.fills and self.now - self.fills[0][3] >= self.fills[0][4]:
            self.commit_fills()

        for p in self.confetti:
            p[3] += 900 * dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[4] -= dt
        self.confetti = [p for p in self.confetti if p[4] > 0]
        for p in self.smoke:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[2] *= 0.97
            p[3] = p[3] * 0.97 - 25 * dt
            p[4] -= dt
        self.smoke = [p for p in self.smoke if p[4] > 0]
        for p in self.twinkles:
            p[2] -= dt
            p[6] += 3 * dt
        self.twinkles = [p for p in self.twinkles if p[2] > 0]

        if self.clear_fx and self.now - self.clear_fx[1] > 0.6:
            self.clear_fx = None
        if self.undo_fx and self.now - self.undo_fx[1] > 0.3:
            self.undo_fx = None

        if self.speak_at is not None and self.now >= self.speak_at:
            self.speak_at = None
            if self.voice:
                try:
                    subprocess.Popen(["spd-say", "-r", "-20", PALETTE[self.color_i][0]],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except OSError:
                    self.voice = False

        self.update_trains(dt)
        # Wiggling the mouse back and forth (looking for it) makes the pointer pop
        # up big. Painting strokes and single long moves don't count.
        self.shake = [m for m in self.shake if self.now - m[0] < 0.6]
        if not self.drawing and self.is_wiggle():
            self.cursor_boost = min(1.0, self.cursor_boost + dt * 6)
        else:
            self.cursor_boost = max(0.0, self.cursor_boost - dt * 1.2)
        self.update_sparkle_runs(dt)

        # Exit only on Ctrl + Shift + Q held together, with no other keys, for 3 s.
        keys = pygame.key.get_pressed()
        self.pressed = {k for k in self.pressed if keys[k]}
        combo = (len(self.pressed) == 3 and self.pressed & CTRL_KEYS
                 and self.pressed & SHIFT_KEYS and pygame.K_q in self.pressed)
        if combo:
            self.exit_hold += dt
            if self.exit_hold >= EXIT_HOLD_SECONDS:
                self.running = False
        else:
            self.exit_hold = 0.0

    # -------------------------------------------------------------- draw
    def draw(self):
        scr = self.screen
        cr = self.canvas_rect
        scr.blit(self.canvas, cr)
        scr.set_clip(cr)

        if self.clear_fx:
            old, start = self.clear_fx
            t = min(1.0, (self.now - start) / 0.6)
            old.set_alpha(round(255 * (1 - t)))
            scr.blit(old, (cr.x, cr.y + round(t * t * cr.h)))

        if self.undo_fx:
            # The undone change fades away rather than vanishing.
            old, start = self.undo_fx
            old.set_alpha(round(255 * (1 - min(1.0, (self.now - start) / 0.3))))
            scr.blit(old, cr)
            old.set_alpha(None)

        for surf, box, (x, y), start, dur in self.fills:
            # Reveal the fill through a circle growing from where it was tapped.
            reach = max(math.hypot(cx - x, cy - y) for cx, cy in
                        (box.topleft, box.topright, box.bottomleft, box.bottomright))
            r = reach * min(1.0, (self.now - start) / dur) ** 0.7
            frame = pygame.Surface(box.size, pygame.SRCALPHA)
            pygame.draw.circle(frame, (255, 255, 255, 255), (x - box.x, y - box.y), r)
            frame.blit(surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            scr.blit(frame, (cr.x + box.x, cr.y + box.y))

        for surf, (x, y), start in self.anims:
            k = ease_out_back(min(1.0, (self.now - start) / 0.3))
            w, h = surf.get_size()
            sw, sh = max(1, round(w * k)), max(1, round(h * k))
            img = pygame.transform.smoothscale(surf, (sw, sh))
            scr.blit(img, img.get_rect(center=(cr.x + x, cr.y + y)))

        self.draw_trains()

        for x, y, _, _, life, max_life, r in self.smoke:
            frac = life / max_life
            d = max(4, round((r + (1 - frac) * 22) * 2 / 4) * 4)
            puff = self.puff_cache.get(d)
            if puff is None:
                puff = self.puff_cache[d] = pygame.transform.smoothscale(self.puff, (d, d))
            puff.set_alpha(round(220 * frac))
            scr.blit(puff, (x - d / 2, y - d / 2))

        for x, y, _, _, life, max_life, col, r in self.confetti:
            pygame.draw.circle(scr, col, (x, y), max(1, r * life / max_life))

        for x, y, life, max_life, r, col, ang in self.twinkles:
            k = math.sin(math.pi * life / max_life)
            draw_sparkle(scr, col, (x, y), r * k, ang)
        self.draw_sparkle_heads()

        self.draw_splash()
        scr.set_clip(None)

        self.draw_toolbar()
        self.draw_stampbar()
        self.draw_palette()
        self.draw_cursor()
        self.draw_locator()
        if self.exit_hold > 0:
            self.draw_exit_progress()
        elif self.now < self.help_until:
            self.draw_exit_help()

    def _make_puff(self):
        s = pygame.Surface((64, 64), pygame.SRCALPHA)
        for r in range(32, 0, -1):
            a = int(210 * (1 - r / 32) ** 0.6)
            pygame.draw.circle(s, (196, 198, 210, a), (32, 32), r)
        return s

    def _make_splash(self):
        big = pygame.font.Font(None, max(80, self.H // 5))
        letters = [big.render(ch, True, RAINBOW[i % len(RAINBOW)]) for i, ch in
                   enumerate("Euan Paint")]
        shadows = [big.render(ch, True, darker(RAINBOW[i % len(RAINBOW)], 0.45)) for i, ch in
                   enumerate("Euan Paint")]
        w = sum(l.get_width() for l in letters) + 10
        h = max(l.get_height() for l in letters) + 10
        title = pygame.Surface((w, h), pygame.SRCALPHA)
        x = 0
        for i, (l, sh) in enumerate(zip(letters, shadows)):
            y = round(math.sin(i * 0.9) * 8) + 5
            title.blit(sh, (x + 5, y + 5))
            title.blit(l, (x, y))
            x += l.get_width()
        hint = self.font.render("Grown-ups: hold Ctrl + Shift + Q for 3 seconds to exit",
                                True, (120, 120, 130))
        return title, hint

    def draw_splash(self):
        t = self.now
        if t > 6:
            return
        title, hint = self.splash
        cr = self.canvas_rect
        title.set_alpha(round(255 * max(0.0, min(1.0, 3.5 - t))))
        hint.set_alpha(round(255 * max(0.0, min(1.0, 6 - t))))
        self.screen.blit(title, title.get_rect(center=(cr.centerx, cr.centery - cr.h * 0.08)))
        self.screen.blit(hint, hint.get_rect(midbottom=(cr.centerx, cr.bottom - 16)))

    def button(self, rect, selected, base=(255, 255, 255)):
        pygame.draw.rect(self.screen, darker(base, 0.75), rect.move(0, 5), border_radius=18)
        fill = (255, 246, 190) if selected else base
        pygame.draw.rect(self.screen, fill, rect, border_radius=18)
        pygame.draw.rect(self.screen, (255, 190, 0) if selected else (200, 200, 210), rect,
                         6 if selected else 3, border_radius=18)

    def draw_toolbar(self):
        scr = self.screen
        pygame.draw.rect(scr, (255, 232, 170), (0, 0, self.TOOL_W, self.H - self.BAR_H))
        for name, r in self.tool_buttons:
            base = (255, 215, 215) if name == "clear" else WHITE
            self.button(r, name == self.tool, base)
            cx, cy, s = r.centerx, r.centery, r.w
            if name == "brush":
                pygame.draw.line(scr, (150, 95, 50), (cx + s * 0.3, cy - s * 0.3),
                                 (cx - s * 0.02, cy + s * 0.02), max(4, round(s * 0.12)))
                pygame.draw.line(scr, (175, 175, 185), (cx, cy), (cx - s * 0.12, cy + s * 0.12),
                                 max(5, round(s * 0.15)))
                pygame.draw.circle(scr, self.color, (cx - s * 0.18, cy + s * 0.18), s * 0.14)
                pygame.draw.circle(scr, darker(self.color), (cx - s * 0.18, cy + s * 0.18),
                                   s * 0.14, 3)
            elif name == "rainbow":
                band = s * 0.036
                c = (cx, cy + s * 0.08)
                for i, col in enumerate(RAINBOW):
                    pygame.draw.circle(scr, col, c, s * 0.4 - i * band,
                                       draw_top_left=True, draw_top_right=True)
                pygame.draw.circle(scr, (255, 246, 190) if self.tool == name else WHITE, c,
                                   s * 0.4 - 7 * band, draw_top_left=True, draw_top_right=True)
                star = self.stamp_surface("star", GOLD, round(s * 0.46))
                scr.blit(star, star.get_rect(center=(cx, cy + s * 0.2)))
            elif name == "railway":
                n = 13
                pts = [(cx - s * 0.4 + i * s * 0.8 / (n - 1),
                        cy + s * 0.2 - s * 0.07 * math.sin(i / (n - 1) * math.pi)) for i in range(n)]
                heads = []
                for i in range(n):
                    a, b = pts[max(0, i - 1)], pts[min(n - 1, i + 1)]
                    d = math.hypot(b[0] - a[0], b[1] - a[1])
                    heads.append(((b[0] - a[0]) / d, (b[1] - a[1]) / d))
                draw_track(scr, [pts[i] for i in range(n)], heads, s * 0.16)
                icon = self.sprite("engine", None, round(s * 0.42), False)
                scr.blit(icon, icon.get_rect(midbottom=(cx - s * 0.12, cy + s * 0.12)))
                car = self.sprite("car", RAINBOW[4], round(s * 0.36), False)
                scr.blit(car, car.get_rect(midbottom=(cx + s * 0.25, cy + s * 0.1)))
            elif name == "glitter":
                spin = self.now * 1.5 if self.tool == name else 0.0
                for dx, dy, rr, col in ((-0.12, -0.1, 0.24, self.color), (0.2, 0.16, 0.15, GOLD),
                                        (0.2, -0.24, 0.09, GOLD), (-0.22, 0.26, 0.1, GOLD)):
                    c = (cx + s * dx, cy + s * dy)
                    draw_sparkle(scr, INK, c, s * rr + 3, spin)
                    draw_sparkle(scr, col, c, s * rr, spin)
            elif name == "bucket":
                body = [(cx - s * 0.26, cy - s * 0.12), (cx + s * 0.14, cy - s * 0.12),
                        (cx + s * 0.08, cy + s * 0.3), (cx - s * 0.2, cy + s * 0.3)]
                pygame.draw.polygon(scr, (150, 165, 185), body)
                pygame.draw.polygon(scr, (60, 65, 75), body, 3)
                handle = pygame.Rect(0, 0, s * 0.4, s * 0.36)
                handle.midbottom = (cx - s * 0.06, cy - s * 0.04)
                pygame.draw.arc(scr, (60, 65, 75), handle, 0, math.pi, 3)
                spill = [(cx + s * 0.14, cy - s * 0.14), (cx + s * 0.3, cy + s * 0.05),
                         (cx + s * 0.3, cy + s * 0.2), (cx + s * 0.2, cy + s * 0.05)]
                paint = (cx - s * 0.26, cy - s * 0.2, s * 0.4, s * 0.12)
                pygame.draw.ellipse(scr, self.color, paint)
                pygame.draw.polygon(scr, self.color, spill)
                pygame.draw.circle(scr, self.color, (cx + s * 0.3, cy + s * 0.27), s * 0.06)
                pygame.draw.ellipse(scr, darker(self.color), paint, 2)
                pygame.draw.circle(scr, darker(self.color), (cx + s * 0.3, cy + s * 0.27),
                                   s * 0.06, 2)
            elif name == "eraser":
                pts = rotated_rect_points(cx, cy, s * 0.6, s * 0.3, -0.6)
                pygame.draw.polygon(scr, (255, 150, 175), pts)
                pygame.draw.polygon(scr, (150, 60, 90), pts, 3)
                tip = rotated_rect_points(cx - s * 0.18 * math.cos(0.6),
                                          cy + s * 0.18 * math.sin(0.6), s * 0.24, s * 0.3, -0.6)
                pygame.draw.polygon(scr, (120, 160, 255), tip)
                pygame.draw.polygon(scr, (40, 70, 160), tip, 3)
            elif name == "size":
                for i, rad in enumerate((0.06, 0.1, 0.15)):
                    col = self.color if i == self.size_i else (205, 205, 215)
                    p = (cx + (i - 1) * s * 0.28, cy)
                    pygame.draw.circle(scr, col, p, s * rad)
                    pygame.draw.circle(scr, darker(col), p, s * rad, 2)
            elif name == "undo":
                col, edge = (60, 150, 255), (25, 70, 160)
                ring = pygame.Rect(0, 0, s * 0.56, s * 0.56)
                ring.center = (cx + s * 0.04, cy + s * 0.04)
                for c, w in ((edge, round(s * 0.15)), (col, round(s * 0.1))):
                    pygame.draw.arc(scr, c, ring, -math.pi * 0.75, math.pi * 0.85, w)
                tip = (ring.centerx + math.cos(math.pi * 0.85) * ring.w / 2,
                       ring.centery - math.sin(math.pi * 0.85) * ring.h / 2)
                head = [(tip[0] - s * 0.2, tip[1] - s * 0.02), (tip[0] + s * 0.06, tip[1] - s * 0.2),
                        (tip[0] + s * 0.08, tip[1] + s * 0.14)]
                pygame.draw.polygon(scr, col, head)
                pygame.draw.polygon(scr, edge, head, 3)
            elif name == "clear":
                can = [(cx - s * 0.22, cy - s * 0.14), (cx + s * 0.22, cy - s * 0.14),
                       (cx + s * 0.17, cy + s * 0.32), (cx - s * 0.17, cy + s * 0.32)]
                pygame.draw.polygon(scr, (130, 140, 155), can)
                pygame.draw.polygon(scr, (60, 65, 75), can, 3)
                for dx in (-0.08, 0, 0.08):
                    pygame.draw.line(scr, (60, 65, 75), (cx + s * dx, cy - s * 0.06),
                                     (cx + s * dx * 0.85, cy + s * 0.25), 3)
                lid = pygame.Rect(0, 0, s * 0.56, s * 0.08)
                lid.center = (cx, cy - s * 0.2)
                pygame.draw.rect(scr, (130, 140, 155), lid, border_radius=4)
                pygame.draw.rect(scr, (60, 65, 75), lid, 3, border_radius=4)
                knob = pygame.Rect(0, 0, s * 0.16, s * 0.07)
                knob.midbottom = lid.midtop
                pygame.draw.rect(scr, (60, 65, 75), knob, 3, border_radius=3)

    def draw_stampbar(self):
        scr = self.screen
        pygame.draw.rect(scr, (195, 232, 255),
                         (self.W - self.TOOL_W, 0, self.TOOL_W, self.H - self.BAR_H))
        icon_size = round(self.stamp_size * 0.8)
        for i, r in self.stamp_buttons:
            self.button(r, self.tool == "stamp" and i == self.stamp_i)
            icon = self.stamp_surface(STAMPS[i], self.color, icon_size)
            scr.blit(icon, icon.get_rect(center=r.center))

    def draw_palette(self):
        scr = self.screen
        top = self.H - self.BAR_H
        pygame.draw.rect(scr, (232, 218, 255), (0, top, self.W, self.BAR_H))
        pygame.draw.line(scr, (190, 170, 230), (0, top), (self.W, top), 4)
        age = max(0.0, self.now - self.color_changed_at)
        for i, ((_, col), (x, y)) in enumerate(zip(PALETTE, self.swatches)):
            r = self.swatch_r
            if i == self.color_i:
                r *= 1.3 + 0.25 * max(0.0, 1 - age * 4) * abs(math.sin(age * 20))
                pygame.draw.circle(scr, INK, (x, y), r + 9)
                pygame.draw.circle(scr, WHITE, (x, y), r + 6)
            pygame.draw.circle(scr, darker(col, 0.7), (x, y + 4), r)
            pygame.draw.circle(scr, col, (x, y), r)
            pygame.draw.circle(scr, darker(col), (x, y), r, 3)

    def draw_cursor(self):
        scr = self.screen
        x, y = self.mouse
        if not self.canvas_rect.collidepoint(self.mouse):
            # Kept fully on screen, even right at the edges.
            r = 20
            x, y = self.locator_pos(r)
            pygame.draw.circle(scr, INK, (x, y), r + 5)
            pygame.draw.circle(scr, WHITE, (x, y), r + 2)
            pygame.draw.circle(scr, self.color, (x, y), r)
            return
        if self.tool == "brush":
            r = self.size["brush"]
            pygame.draw.circle(scr, self.color, (x, y), r)
            pygame.draw.circle(scr, INK, (x, y), r + 2, 2)
            pygame.draw.circle(scr, WHITE, (x, y), r + 3, 1)
        elif self.tool == "railway":
            tx, ty = self.tdir
            pts = [(x + tx * (i - 6) * 4, y + ty * (i - 6) * 4) for i in range(13)]
            draw_track(scr, pts, [self.tdir] * 13, self.size["gauge"])
            pygame.draw.circle(scr, INK, (x, y), 5)
            pygame.draw.circle(scr, WHITE, (x, y), 3)
        elif self.tool == "glitter":
            r = self.size["brush"] + 10
            draw_sparkle(scr, INK, (x, y), r + 4, self.now * 2)
            draw_sparkle(scr, self.color if self.color != WHITE else GOLD, (x, y), r, self.now * 2)
        elif self.tool == "bucket":
            # A paint drop hanging under the pointer tip.
            pygame.draw.circle(scr, INK, (x, y + 36), 21)
            pygame.draw.polygon(scr, INK, [(x, y - 6), (x - 21, y + 30), (x + 21, y + 30)])
            pygame.draw.circle(scr, self.color, (x, y + 36), 17)
            pygame.draw.polygon(scr, self.color, [(x, y), (x - 17, y + 31), (x + 17, y + 31)])
            pygame.draw.circle(scr, WHITE, (x - 6, y + 32), 4)
        elif self.tool == "eraser":
            r = self.size["eraser"]
            pygame.draw.circle(scr, WHITE, (x, y), r)
            pygame.draw.circle(scr, (150, 60, 90), (x, y), r, 3)
        elif self.tool == "stamp":
            ghost = self.stamp_surface(STAMPS[self.stamp_i], self.color, self.size["stamp"])
            ghost.set_alpha(150)
            scr.blit(ghost, ghost.get_rect(center=(x, y)))
            ghost.set_alpha(255)
        elif self.tool == "rainbow":
            star = self.stamp_surface("star", GOLD, 60 + self.size["stripe"] * 4)
            star = pygame.transform.rotozoom(star, math.sin(self.now * 3) * 12, 1)
            scr.blit(star, star.get_rect(center=(x, y)))

    def is_wiggle(self):
        dist = sum(math.hypot(dx, dy) for _, dx, dy in self.shake)
        turns = 0
        for axis in (1, 2):
            signs = [1 if m[axis] > 0 else -1 for m in self.shake if abs(m[axis]) > 4]
            turns += sum(1 for a, b in zip(signs, signs[1:]) if a != b)
        return turns >= 4 and dist > 600

    def locator_pos(self, r):
        x, y = self.mouse
        return min(max(x, r + 5), self.W - r - 6), min(max(y, r + 5), self.H - r - 6)

    def draw_locator(self):
        """Rainbow ripples around the pointer near the screen edges or when the mouse is wiggled."""
        scr = self.screen
        x, y = self.mouse
        edge = min(x, y, self.W - 1 - x, self.H - 1 - y)
        strength = max(self.cursor_boost, 1 - edge / 70)
        if strength <= 0:
            return
        for k in range(3):
            ph = (self.now * 1.1 + k / 3) % 1
            r = 24 + ph * 110 * (0.6 + 0.4 * strength)
            col = RAINBOW[(int(self.now * 4) + k * 2) % len(RAINBOW)]
            pygame.draw.circle(scr, col, (x, y), r, max(2, round(9 * (1 - ph))))
        if self.cursor_boost > 0:
            r = 18 + 42 * self.cursor_boost
            pos = self.locator_pos(r)
            pygame.draw.circle(scr, INK, pos, r + 5)
            pygame.draw.circle(scr, WHITE, pos, r + 2)
            pygame.draw.circle(scr, self.color, pos, r)

    def draw_exit_progress(self):
        scr = self.screen
        panel = pygame.Rect(0, 0, 620, 120)
        panel.midtop = (self.W // 2, 30)
        shade = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(shade, (20, 20, 30, 215), shade.get_rect(), border_radius=24)
        scr.blit(shade, panel)
        ring = pygame.Rect(0, 0, 80, 80)
        ring.midleft = (panel.x + 24, panel.centery)
        pygame.draw.circle(scr, (80, 80, 95), ring.center, 40, 8)
        p = min(1.0, self.exit_hold / EXIT_HOLD_SECONDS)
        pygame.draw.arc(scr, (255, 200, 0), ring, math.pi / 2 - 2 * math.pi * p, math.pi / 2, 8)
        msg = self.font.render("Keep holding to exit...", True, WHITE)
        sub = self.font.render("(the picture will be saved)", True, (190, 190, 200))
        scr.blit(msg, (ring.right + 24, panel.centery - msg.get_height() - 2))
        scr.blit(sub, (ring.right + 24, panel.centery + 4))

    def draw_exit_help(self):
        scr = self.screen
        fade = min(1.0, self.help_until - self.now)
        panel = pygame.Rect(0, 0, 720, 250)
        panel.center = self.canvas_rect.center
        shade = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(shade, (20, 20, 30, 230), shade.get_rect(), border_radius=28)
        title = self.font.render("To close Euan Paint, hold these keys together:", True, WHITE)
        shade.blit(title, title.get_rect(midtop=(panel.w / 2, 28)))
        big = pygame.font.Font(None, 64)
        caps = [big.render(k, True, INK) for k in ("Ctrl", "Shift", "Q")]
        plus = big.render("+", True, WHITE)
        widths = [c.get_width() + 44 for c in caps]
        x = (panel.w - sum(widths) - 2 * (plus.get_width() + 30)) / 2
        for i, (cap, w) in enumerate(zip(caps, widths)):
            key = pygame.Rect(round(x), 88, w, 82)
            pygame.draw.rect(shade, (150, 150, 165), key.move(0, 6), border_radius=14)
            pygame.draw.rect(shade, (245, 245, 250), key, border_radius=14)
            shade.blit(cap, cap.get_rect(center=key.center))
            x += w
            if i < 2:
                shade.blit(plus, plus.get_rect(center=(x + (plus.get_width() + 30) / 2, key.centery)))
                x += plus.get_width() + 30
        sub = self.font.render(f"for {EXIT_HOLD_SECONDS:g} seconds. The picture is saved automatically.",
                               True, (200, 200, 215))
        shade.blit(sub, sub.get_rect(midbottom=(panel.w / 2, panel.h - 26)))
        shade.set_alpha(round(255 * fade))
        scr.blit(shade, panel)

    # --------------------------------------------------------------- run
    def run(self):
        self.grab()
        clock = pygame.time.Clock()
        start = time.monotonic()
        while self.running:
            dt = clock.tick(60) / 1000
            self.now = time.monotonic() - start
            for e in pygame.event.get():
                self.handle(e)
            self.update(dt)
            self.draw()
            pygame.display.flip()
        self.commit_anims()
        self.commit_fills()
        self.autosave()


def open_display(windowed):
    # Prefer native Wayland: it lets us inhibit desktop shortcuts (Super, Alt+Tab).
    if "SDL_VIDEODRIVER" not in os.environ and os.environ.get("WAYLAND_DISPLAY"):
        os.environ["SDL_VIDEODRIVER"] = "wayland"
        try:
            pygame.display.init()
        except pygame.error:
            del os.environ["SDL_VIDEODRIVER"]
    if not pygame.display.get_init():
        pygame.display.init()
    pygame.display.set_caption("Euan Paint")
    pygame.display.set_icon(make_icon(64))
    if windowed:
        screen = pygame.display.set_mode((1280, 800))
    else:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.mouse.set_visible(False)
    return screen


def main():
    ap = argparse.ArgumentParser(description="Euan Paint - a painting app for little ones")
    ap.add_argument("--windowed", action="store_true",
                    help="run in a normal window that can be closed (for grown-ups testing)")
    ap.add_argument("--no-sound", action="store_true", help="turn off sound effects")
    ap.add_argument("--no-voice", action="store_true", help="don't speak colour names")
    ap.add_argument("--make-icon", metavar="PNG", help="write the app icon to PNG and exit")
    args = ap.parse_args()

    if args.make_icon:
        pygame.image.save(make_icon(256), args.make_icon)
        return

    screen = open_display(args.windowed)
    pygame.font.init()
    sounds = Sounds(enabled=not args.no_sound)
    App(screen, sounds, voice=not args.no_voice, windowed=args.windowed).run()
    pygame.quit()


if __name__ == "__main__":
    main()
