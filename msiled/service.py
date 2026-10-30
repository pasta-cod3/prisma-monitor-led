import copy
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import models, steelseries
from .common import hex_to_rgb

HOST, PORT = "127.0.0.1", int(os.environ.get("MONITOR_LED_PORT", "7878"))
DASHBOARD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard")
STATE_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "monitor-led")
STATE_FILE = os.path.join(STATE_DIR, "state.json")
PERSIST_DELAY = 3.0
POLL = 2.0
MODELS_BY_ID = {m["id"]: m for m in models.MODELS + [models.GENERIC_STEEL]}


def default_state(model):
    return {"brightness": 100,
            "zones": {z["id"]: {"effect": "static", "colors": ["#ff2a2a"], "speed": 20} for z in model["zones"]}}


def validate(model, state):
    out = default_state(model)
    out["brightness"] = max(0, min(100, int(state.get("brightness", 100))))
    zones = {z["id"]: z for z in model["zones"]}
    for zid, cfg in state.get("zones", {}).items():
        if zid not in zones:
            raise ValueError("zona sconosciuta per %s: %s" % (model["id"], zid))
        effect = cfg.get("effect", "static")
        if effect not in model["effects"]:
            raise ValueError("effetto non disponibile su %s: %s" % (model["id"], effect))
        if effect == "leds" and zid not in model["per_led"]:
            raise ValueError("questa zona non si puo' colorare LED per LED")
        limit = zones[zid]["leds"] if effect == "leds" else steelseries.MAX_COLORS
        colors = [c for c in cfg.get("colors", []) if isinstance(c, str)][:limit]
        for c in colors:
            hex_to_rgb(c)
        out["zones"][zid] = {"effect": effect, "colors": colors or ["#ffffff"],
                             "speed": max(1, min(100, int(cfg.get("speed", 20))))}
    return out


class Store:

    def __init__(self):
        self.monitors, self.legacy = {}, None
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        if "monitors" in data:
            for key, entry in data["monitors"].items():
                model = MODELS_BY_ID.get(entry.get("model"))
                if model:
                    try:
                        self.monitors[key] = {"model": model["id"], "state": validate(model, entry.get("state", {}))}
                    except (ValueError, TypeError):
                        pass
        else:
            self.legacy = data

    def get(self, key, model):
        if key not in self.monitors:
            state = default_state(model)
            if self.legacy and model["id"] == "MPG27CQ":
                try:
                    state = validate(model, self.legacy)
                except (ValueError, TypeError):
                    pass
                self.legacy = None
            self.monitors[key] = {"model": model["id"], "state": state}
            self.save()
        return self.monitors[key]["state"]

    def set(self, key, state):
        self.monitors[key]["state"] = state
        self.save()

    def save(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"version": 2, "monitors": self.monitors}, f, indent=2)
        os.replace(tmp, STATE_FILE)


class Slot:

    def __init__(self, device):
        self.device = device
        self.backend = models.open_backend(device)
        self.applied = None
        self.persisted = None
        self.persist_at = None


class Controller:
    def __init__(self):
        self.store = Store()
        self.detector = models.Detector()
        self.lock = threading.Condition()
        self.versions = {}
        self.identify = {}
        self.slots = {}
        self.errors = {}
        self.notes = []

    def set_state(self, key, state):
        with self.lock:
            entry = self.store.monitors.get(key)
            if not entry:
                raise ValueError("monitor sconosciuto: %s" % key)
            self.store.set(key, validate(MODELS_BY_ID[entry["model"]], state))
            self.versions[key] = self.versions.get(key, 0) + 1
            self.lock.notify()

    def request_identify(self, key, zone):
        with self.lock:
            entry = self.store.monitors.get(key)
            if not entry or zone not in {z["id"] for z in MODELS_BY_ID[entry["model"]]["zones"]}:
                raise ValueError("monitor o zona sconosciuti")
            if key not in self.slots:
                raise ValueError("il monitor non e' collegato via USB")
            self.identify[key] = zone
            self.lock.notify()

    def status(self):
        with self.lock:
            monitors = []
            for key, entry in self.store.monitors.items():
                slot = self.slots.get(key)
                monitors.append({"key": key, "model": models.public(MODELS_BY_ID[entry["model"]]),
                                 "connected": slot is not None, "device": slot.device["path"] if slot else None,
                                 "error": self.errors.get(key), "state": entry["state"]})
            monitors.sort(key=lambda m: not m["connected"])
            return {"monitors": monitors, "notes": self.notes,
                    "supported": [m["name"] for m in models.MODELS]}

    def _sync_devices(self):
        devices, notes = self.detector.scan()
        found = {d["key"]: d for d in devices}
        for key in list(self.slots):
            if key not in found or found[key]["path"] != self.slots[key].device["path"]:
                self.slots.pop(key).backend.close()
        for key, device in found.items():
            if key not in self.slots:
                with self.lock:
                    self.store.get(key, device["model"])
                try:
                    self.slots[key] = Slot(device)
                    self.errors.pop(key, None)
                except OSError as e:
                    self.errors[key] = "impossibile aprire %s: %s" % (device["path"], e)
        self.notes = notes

    def run(self):
        first = True
        while True:
            with self.lock:
                idle = all(self.versions.get(k, 0) == s.applied for k, s in self.slots.items()) and not self.identify
                if idle and not first:
                    self.lock.wait(timeout=POLL)
            first = False
            self._sync_devices()
            with self.lock:
                for key in [k for k in self.identify if k not in self.slots]:
                    del self.identify[key]
            for key, slot in list(self.slots.items()):
                with self.lock:
                    state = copy.deepcopy(self.store.monitors[key]["state"])
                    version = self.versions.get(key, 0)
                    zone = self.identify.pop(key, None)
                try:
                    if zone:
                        slot.backend.identify(zone)
                        slot.applied = None
                    if version != slot.applied:
                        slot.backend.apply(state)
                        if slot.persisted is not None and version != slot.persisted:
                            slot.persist_at = time.monotonic() + PERSIST_DELAY
                        slot.applied = version
                        if slot.persisted is None:
                            slot.persisted = version
                    if slot.persist_at and time.monotonic() >= slot.persist_at:
                        slot.backend.persist()
                        slot.persisted, slot.persist_at = slot.applied, None
                    self.errors.pop(key, None)
                except OSError as e:
                    self.errors[key] = str(e)
                    self.slots.pop(key).backend.close()


controller = Controller()


class Handler(BaseHTTPRequestHandler):
    FILES = {"/": ("index.html", "text/html; charset=utf-8"),
             "/i18n.js": ("i18n.js", "text/javascript; charset=utf-8"),
             "/manifest.json": ("manifest.json", "application/manifest+json"),
             "/fonts/instrument-sans.woff2": ("fonts/instrument-sans.woff2", "font/woff2")}

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/status":
            return self._send(200, controller.status())
        if path in self.FILES:
            name, ctype = self.FILES[path]
            with open(os.path.join(DASHBOARD, name), "rb") as f:
                return self._send(200, f.read(), ctype)
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.headers.get("Origin") not in (None, "http://%s:%d" % (HOST, PORT), "http://localhost:%d" % PORT):
            return self._send(403, {"error": "origine non consentita"})
        if self.headers.get("Content-Type") != "application/json":
            return self._send(415, {"error": "serve application/json"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/state":
                controller.set_state(body.get("key"), body.get("state", {}))
            elif self.path == "/api/identify":
                controller.request_identify(body.get("key"), body.get("zone"))
            else:
                return self._send(404, {"error": "not found"})
        except (ValueError, TypeError, AttributeError) as e:
            return self._send(400, {"error": str(e)})
        self._send(200, controller.status())


def main():
    threading.Thread(target=controller.run, daemon=True).start()
    print("Dashboard LED: http://%s:%d" % (HOST, PORT), flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
