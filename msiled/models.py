from . import edid, hidraw, mystic, steelseries

FRONT_BARS = [
    {"id": "G%d" % (i + 1), "label": "Barra frontale %d" % (i + 1), "tkey": "z_front", "tn": i + 1,
     "view": "front", "leds": 8, "range": (i * 8, i * 8 + 7)} for i in range(5)
]

STEEL_LAYOUTS = {
    "MPG27CQ": FRONT_BARS + [
        {"id": "G7", "label": "Retro sinistra", "tkey": "z_back_left", "view": "back", "shape": "bracket-left", "leds": 40, "range": (0x3F, 0x66)},
        {"id": "G6", "label": "Retro destra", "tkey": "z_back_right", "view": "back", "shape": "bracket-right", "leds": 23, "range": (0x28, 0x3E)},
    ],
    "generic": [{"id": "ALL", "label": "Tutti i LED", "tkey": "z_all", "view": "back", "shape": "bar", "leds": 103, "range": (0x00, 0x66)}],
}

MYSTIC_ZONES = [{"id": "M1", "label": "Mystic Light", "tkey": "z_mystic", "view": "back", "shape": "ring", "group": 1, "leds": 9}]
OPTIX_ZONES = [
    {"id": "M0", "label": "Gruppo LED 1", "tkey": "z_group", "tn": 1, "view": "back", "shape": "bar", "group": 0, "leds": 24},
    {"id": "M1", "label": "Gruppo LED 2", "tkey": "z_group", "tn": 2, "view": "back", "shape": "bar", "group": 1, "leds": 24},
]


def _model(mid, ids, backend, zones, tested=False, variant=None, name=None):
    return {"id": mid, "name": name or "MSI " + mid, "ids": ids, "backend": backend, "variant": variant,
            "zones": zones, "tested": tested,
            "effects": list(steelseries.EFFECTS if backend == "steelseries" else mystic.EFFECTS),
            "per_led": [z["id"] for z in zones if backend == "mystic" or z["view"] == "front"]}


MODELS = [
    _model("MPG27CQ", [("001", "V18")], "steelseries", STEEL_LAYOUTS["MPG27CQ"], tested=True, name="MSI Optix MPG27CQ"),
    _model("MPG341CQR", [("00>", "V09")], "steelseries", STEEL_LAYOUTS["generic"], name="MSI Optix MPG341CQR"),
    _model("MAG321CURV", [("00;", "V18"), ("00;", "V43")], "mystic", MYSTIC_ZONES, variant="mystic"),
    _model("MAG321CQR", [("00:", "V18")], "mystic", MYSTIC_ZONES, variant="mystic"),
    _model("MAG241CR", [("004", "V18")], "mystic", MYSTIC_ZONES, variant="mystic"),
    _model("MAG271CR", [("005", "V18")], "mystic", MYSTIC_ZONES, variant="mystic"),
    _model("MAG271CQR", [("006", "V19")], "mystic", MYSTIC_ZONES, variant="mystic"),
    _model("MAG272CQR", [("00E", "V18"), ("00E", "V41")], "mystic", MYSTIC_ZONES, variant="mystic"),
    _model("MAG272QP", [("00O", "V18")], "mystic", MYSTIC_ZONES, variant="mystic"),
    _model("MAG251RX", [("00B", "V18")], "mystic", MYSTIC_ZONES, variant="mystic"),
    _model("MPG273CQR", [("00[", "V51")], "mystic", [
        {"id": "M0", "label": "Logo", "tkey": "z_logo", "view": "back", "shape": "ring", "group": 0, "leds": 9},
        {"id": "M1", "label": "Freccia", "tkey": "z_arrow", "view": "back", "shape": "chevron", "group": 1, "leds": 15},
    ], variant="optix"),
    _model("MAG274R", [("00Z", "V41")], "mystic", OPTIX_ZONES, variant="optix"),
    _model("MAG274QRF-QD", [("00e", "V43"), ("00e", "V48"), ("00e", "V56")], "mystic", OPTIX_ZONES, variant="optix"),
    _model("MAG274QRX", [("00|", "V43")], "mystic", OPTIX_ZONES, variant="optix"),
]

GENERIC_STEEL = _model("SteelSeries", [], "steelseries", STEEL_LAYOUTS["generic"],
                       name="Monitor MSI con LED SteelSeries (modello non riconosciuto)")


def by_identity(ident):
    return next((m for m in MODELS if ident in m["ids"]), None) if ident else None


def by_edid(names, backend):
    hits = set()
    for name in names:
        n = edid.normalize(name)
        for m in MODELS:
            mid = edid.normalize(m["id"])
            if m["backend"] == backend and n and (n == mid or (len(name) >= 13 and mid.startswith(n))):
                hits.add(m["id"])
    if len(hits) != 1:
        return None
    mid = hits.pop()
    return next(m for m in MODELS if m["id"] == mid)


def public(model):
    keep = ("id", "label", "tkey", "tn", "view", "shape", "leds")
    return {"id": model["id"], "name": model["name"], "backend": model["backend"], "tested": model["tested"],
            "effects": model["effects"], "per_led": model["per_led"],
            "zones": [{k: z[k] for k in keep if k in z} for z in model["zones"]]}


class Detector:

    def __init__(self):
        self.identities = {}

    def _identity(self, node):
        if node.port not in self.identities:
            try:
                self.identities[node.port] = ("ok", mystic.identify(node.dev))
            except PermissionError:
                return ("permission", None)
            except OSError as e:
                self.identities[node.port] = ("error: %s" % e, None)
        return self.identities[node.port]

    def scan(self):
        nodes = hidraw.nodes()
        names = [m["name"] for m in edid.monitors() if m["vendor"] == "MSI" or m["name"].upper().startswith("MSI")]
        controllers = [n for n in nodes if (n.vid, n.pid) == (mystic.VID, mystic.PID)]
        steels = [n for n in nodes if (n.vid, n.pid) == (steelseries.VID, steelseries.PID)
                  and n.interface == steelseries.INTERFACE]
        present = {n.port for n in nodes}
        self.identities = {p: v for p, v in self.identities.items() if p in present}

        devices, notes, paired = [], [], set()
        for s in steels:
            ctrl = next((c for c in controllers if c.hub and c.hub == s.hub), None)
            model = None
            if ctrl:
                paired.add(ctrl.port)
                status, ident = self._identity(ctrl)
                model = by_identity(ident)
                if model and model["backend"] != "steelseries":
                    model = None
            model = model or by_edid(names, "steelseries") or GENERIC_STEEL
            key = (ctrl.serial if ctrl and ctrl.serial else "usb-" + s.port) + "-" + model["id"]
            devices.append({"key": key, "model": model, "path": s.dev, "backend": "steelseries"})

        for c in controllers:
            if c.port in paired:
                continue
            status, ident = self._identity(c)
            model = by_identity(ident)
            if status == "permission":
                model = by_edid(names, "mystic")
                if not model:
                    notes.append({"code": "note_permission", "args": [c.dev]})
                    continue
            if not model:
                notes.append({"code": "note_unknown", "args": [str(ident)]})
                continue
            if model["backend"] != "mystic":
                continue
            key = (c.serial or "usb-" + c.port) + "-" + model["id"]
            devices.append({"key": key, "model": model, "path": c.dev, "backend": "mystic"})

        if not devices and names:
            notes.append({"code": "note_video", "args": [", ".join(names)]})
        return devices, notes


NOTE_IT = {
    "note_permission": "Trovato un monitor MSI su %s ma mancano i permessi per leggerlo: esegui install.sh per aggiungere la regola udev.",
    "note_unknown": "Monitor MSI non riconosciuto (identificativi %s): apri una segnalazione su GitHub con questo testo.",
    "note_video": "Collegato via video: %s. Per comandare i LED collega anche il cavo USB (presa USB-B dietro al monitor) al computer.",
}


def note_text(note):
    return NOTE_IT.get(note["code"], note["code"]) % tuple(note["args"])


def open_backend(device):
    if device["backend"] == "steelseries":
        return steelseries.SteelSeriesMLC(device["path"], device["model"])
    return mystic.MysticLight(device["path"], device["model"])
