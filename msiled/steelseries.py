import time

from .common import RAINBOW, hex_to_rgb, pad
from .hidraw import Device

VID, PID = 0x1038, 0x1126
INTERFACE = 0

FEATURE_LEN = 525
COMMAND_LEN = 65
MIN_STEP = 0x21
MAX_COLORS = 12
EFFECTS = ("off", "static", "breathing", "cycle", "rainbow", "leds")


def _transition(delta16, total, budget):
    qs = [d // total for d in delta16]
    splits = [d - q * total for d, q in zip(delta16, qs)]
    points = [0]
    if budget >= 2:
        candidates = sorted(set(splits))
        if budget < 4:
            candidates = [sorted(splits)[1]]
        for b in candidates:
            p = min(max(b, points[-1] + MIN_STEP), total - MIN_STEP)
            if p - points[-1] >= MIN_STEP:
                points.append(p)
    points.append(total)

    snapped = [max(p for p in points if p <= b) if d >= 0 else min(p for p in points if p >= b)
               for b, d in zip(splits, delta16)]
    return [(points[j + 1] - points[j], tuple(q + (1 if points[j] < sb else 0) for q, sb in zip(qs, snapped)))
            for j in range(len(points) - 1)]


class SteelSeriesMLC:
    def __init__(self, path, model):
        self.path = path
        self.model = model
        self.ranges = {z["id"]: tuple(z["range"]) for z in model["zones"]}
        self.dev = Device(path)

    def close(self):
        self.dev.close()


    def _command(self, cmd, sub=0):
        buf = bytearray(COMMAND_LEN)
        buf[1], buf[3] = cmd, sub
        self.dev.write(buf)

    def _led_records(self, start, end, entry):
        for first in range(start, end + 1, 40):
            last = min(first + 39, end)
            buf = bytearray(FEATURE_LEN)
            buf[1] = 0x0E
            buf[3] = last - first + 1
            for i, led in enumerate(range(first, last + 1)):
                o = 5 + i * 12
                buf[o:o + 12] = entry(led)
            self.dev.send_feature(buf)


    def fill_range(self, start, end, rgb):
        self._led_records(start, end, lambda n: bytes([*rgb, 0, 0, 0, 0, 0, 0, 1, 0, n]))

    def set_colors(self, zone, rgbs):
        start, end = self.ranges[zone]
        pick = lambda n: rgbs[min(n - start, len(rgbs) - 1)]
        self._led_records(start, end, lambda n: bytes([*pick(n), 0, 0, 0, 0, 0, 0, 1, 0, n]))

    def set_profile_range(self, start, end, profile):
        self._led_records(start, end, lambda n: bytes([0, 0, 0, 0, 0, 0, 0, 0, profile, 0, 0, n]))

    def set_profile(self, zone, profile):
        self.set_profile_range(*self.ranges[zone], profile)

    def define_profile(self, profile, colors, speed):
        n = len(colors)
        if not 1 <= n <= MAX_COLORS:
            raise ValueError("da 1 a %d colori" % MAX_COLORS)
        target = speed * 100
        steps, last_p = [], 0
        for i in range(n):
            step = min(0xFFFF, max(MIN_STEP, target * (i + 1) // n - last_p))
            last_p += step
            steps.append(step)

        entries, pos = [], [c * 16 for c in colors[0]]
        for i in range(n):
            after = n - 1 - i
            budget = min(4, 16 - len(entries) - (after - 1 + 4 if after else 0))
            target = [c * 16 for c in colors[(i + 1) % n]]
            for dur, deltas in _transition([t - p for t, p in zip(target, pos)], steps[i], budget):
                entries.append((dur, deltas))
                pos = [p + d * dur for p, d in zip(pos, deltas)]

        buf = bytearray(FEATURE_LEN)
        buf[1] = 0x0B
        for i, (dur, deltas) in enumerate(entries):
            o = 3 + i * 8
            buf[o] = profile if i == 0 else i
            for k in range(3):
                buf[o + 2 + k] = deltas[k] & 0xFF
            buf[o + 6], buf[o + 7] = dur & 0xFF, dur >> 8
        o = 3 + 16 * 8
        buf[o:o + 8] = bytes([0, 0, 0xF0, 0x0F, 0, 0, 0, 0])
        buf[o + 8], buf[o + 10], buf[o + 12] = colors[0]
        o += 16
        total_steps = sum(steps)
        buf[o + 2], buf[o + 3] = 0x80, 0x00
        buf[o + 4] = len(entries)
        buf[o + 6], buf[o + 7] = total_steps & 0xFF, (total_steps >> 8) & 0xFF
        self.dev.send_feature(buf)


    def brightness(self, value):
        self._command(0x0C, max(0, min(255, value)))

    def flush(self):
        self._command(0x0D, 0x02)

    def persist(self):
        self._command(0x09)


    def apply(self, state):
        self.brightness(round(state["brightness"] * 255 / 100))
        for i, zone in enumerate(self.model["zones"]):
            cfg = state["zones"][zone["id"]]
            rgbs = [hex_to_rgb(c) for c in cfg["colors"]]
            effect = cfg["effect"]
            if effect in ("off", "static", "leds"):
                self.set_profile(zone["id"], 0)
                if effect == "leds":
                    self.set_colors(zone["id"], pad(rgbs, zone["leds"]))
                else:
                    self.set_colors(zone["id"], [(0, 0, 0) if effect == "off" else rgbs[0]])
            else:
                if effect == "breathing":
                    rgbs = [rgbs[0], (0, 0, 0)]
                elif effect == "rainbow":
                    rgbs = [hex_to_rgb(c) for c in RAINBOW]
                profile = i + 1
                self.define_profile(profile, rgbs[:MAX_COLORS], cfg["speed"])
                self.set_profile(zone["id"], profile)
        self.flush()

    def identify(self, zone):
        self.brightness(255)
        for _ in range(3):
            for z in self.ranges:
                self.set_profile(z, 0)
                self.set_colors(z, [(255, 255, 255) if z == zone else (0, 0, 0)])
            self.flush()
            time.sleep(0.35)
            self.set_colors(zone, [(0, 0, 0)])
            self.flush()
            time.sleep(0.25)
