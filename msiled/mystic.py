import time

from .common import hex_to_rgb, pad
from .hidraw import Device

VID, PID = 0x1462, 0x3FA4

MODES = {
    "off": 0x00, "static": 0x01, "breathing": 0x02, "blinking": 0x03, "flashing": 0x05,
    "blinds": 0x06, "meteor": 0x08, "rainbow": 0x1A, "random": 0x1F,
}
EFFECTS = ("off", "static", "breathing", "blinking", "flashing", "blinds", "meteor", "rainbow", "random", "leds")

VARIANTS = {"mystic": (0x71, 9), "optix": (0x72, 24)}
GROUP_HEADER = 11


def query(dev, setting, timeout=1.0):
    cmd = "58" + setting
    buf = bytearray(64)
    buf[0] = 0x01
    payload = (cmd + "\r").encode()
    buf[1:1 + len(payload)] = payload
    dev.drain()
    dev.write(buf)
    for _ in range(4):
        data = dev.read(64, timeout)
        if not data:
            return None
        text = "".join(chr(b) if b else "_" for b in data[1:]).split("\r", 1)[0]
        if text.startswith("5b" + setting):
            return text[len(cmd):]
    return None


def identify(path):
    dev = Device(path)
    try:
        p140 = query(dev, "00140")
        p150 = query(dev, "00150") if p140 is not None else None
        return (p140, p150) if p150 is not None else None
    finally:
        dev.close()


class MysticLight:
    def __init__(self, path, model):
        self.path = path
        self.model = model
        self.report_id, self.max_leds = VARIANTS[model["variant"]]
        self.dev = Device(path)

    def close(self):
        self.dev.close()

    def _record(self, groups):
        n = self.max_leds
        buf = bytearray(1 + 2 * GROUP_HEADER + 2 * n * 3 + 1)
        buf[0] = self.report_id
        for g in range(2):
            mode, brightness, leds = groups.get(g, (0, 100, [(255, 255, 255)]))
            o = 1 + g * GROUP_HEADER
            buf[o:o + GROUP_HEADER] = bytes([mode, 0xFF, 0xFF, 0xFF, 0x01, brightness, 0x00, 0xFF, 0x00, 0x80, 0x00])
            o = 1 + 2 * GROUP_HEADER + g * n * 3
            for i, rgb in enumerate(pad(leds, n)):
                buf[o + i * 3:o + i * 3 + 3] = bytes(rgb)
        self.dev.send_feature(buf)

    def apply(self, state):
        groups = {}
        brightness = max(0, min(100, state["brightness"]))
        for zone in self.model["zones"]:
            cfg = state["zones"][zone["id"]]
            rgbs = [hex_to_rgb(c) for c in cfg["colors"]]
            effect = cfg["effect"]
            if effect == "leds":
                groups[zone["group"]] = (MODES["static"], brightness, pad(rgbs, zone["leds"]))
            else:
                groups[zone["group"]] = (MODES[effect], brightness, [rgbs[0]])
        self._record(groups)

    def persist(self):
        pass

    def identify(self, zone):
        group = next(z["group"] for z in self.model["zones"] if z["id"] == zone)
        for _ in range(3):
            self._record({group: (MODES["static"], 100, [(255, 255, 255)])})
            time.sleep(0.35)
            self._record({group: (MODES["off"], 100, [(0, 0, 0)])})
            time.sleep(0.25)
