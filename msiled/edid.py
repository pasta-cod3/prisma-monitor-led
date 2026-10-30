import glob
import os


def _name(edid):
    if len(edid) < 128:
        return None, None
    m = (edid[8] << 8) | edid[9]
    vendor = "".join(chr(((m >> s) & 31) + 64) for s in (10, 5, 0))
    for o in range(54, 126, 18):
        block = edid[o:o + 18]
        if block[0] == 0 and block[1] == 0 and block[3] == 0xFC:
            return vendor, block[5:].split(b"\n")[0].decode("ascii", "replace").strip()
    return vendor, None


def monitors():
    found = []
    for path in sorted(glob.glob("/sys/class/drm/card*-*")):
        try:
            with open(os.path.join(path, "status")) as f:
                if f.read().strip() != "connected":
                    continue
            with open(os.path.join(path, "edid"), "rb") as f:
                vendor, name = _name(f.read())
        except OSError:
            continue
        if vendor:
            found.append({"connector": os.path.basename(path).split("-", 1)[1], "vendor": vendor, "name": name or ""})
    return found


def normalize(name):
    name = name.upper()
    for word in ("MSI", "OPTIX"):
        name = name.replace(word, "")
    return "".join(ch for ch in name if ch.isalnum())
