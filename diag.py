#!/usr/bin/env python3
import json
import time
import urllib.request

from msiled import models

KNOWN = (0x00, 0x66)
UNKNOWN = (0x67, 0xFE)
STEP = 6


def fill(dev, start, end, rgb):
    dev.set_profile_range(start, end, 0)
    dev.fill_range(start, end, rgb)


def step(dev, text, actions):
    print(text, flush=True)
    for start, end, rgb in actions:
        fill(dev, start, end, rgb)
    dev.flush()
    time.sleep(STEP)


def main():
    devices, notes = models.Detector().scan()
    steel = [d for d in devices if d["backend"] == "steelseries"]
    if not steel:
        raise SystemExit("Nessun monitor con controller SteelSeries collegato via USB. " + " ".join(notes))
    device = steel[0]
    print("Monitor: %s (%s)" % (device["model"]["name"], device["path"]))
    dev = models.open_backend(device)
    try:
        dev.brightness(255)
        step(dev, "1) Tutti i LED conosciuti BIANCHI: annota quali restano spenti o di un altro colore.",
             [(*KNOWN, (255, 255, 255))])
        step(dev, "2) Tutti i LED conosciuti ROSSI.", [(*KNOWN, (255, 0, 0))])
        step(dev, "3) LED conosciuti spenti, indici sconosciuti VERDI: si accende qualcosa?",
             [(*KNOWN, (0, 0, 0)), (*UNKNOWN, (0, 255, 0))])
        for zone in device["model"]["zones"]:
            start, end = zone["range"]
            step(dev, "4) Solo %s (LED %d-%d) BLU: dove si accende?" % (zone["label"], start, end),
                 [(0x00, 0xFE, (0, 0, 0)), (start, end, (0, 0, 255))])
        print("5) Il primo LED di ogni gruppo da 8 in ROSSO, l'ultimo in BLU: indica il verso delle barre.")
        fill(dev, 0x00, 0xFE, (0, 0, 0))
        for first in range(KNOWN[0], KNOWN[1] + 1, 8):
            fill(dev, first, first, (255, 0, 0))
            fill(dev, min(first + 7, KNOWN[1]), min(first + 7, KNOWN[1]), (0, 0, 255))
        dev.flush()
        time.sleep(STEP * 2)
        fill(dev, *UNKNOWN, (0, 0, 0))
        dev.flush()
    finally:
        dev.close()

    print("Fine. Riapplico le impostazioni della dashboard...")
    try:
        with urllib.request.urlopen("http://127.0.0.1:7878/api/status") as r:
            monitors = json.load(r)["monitors"]
        for m in monitors:
            req = urllib.request.Request("http://127.0.0.1:7878/api/state",
                                         json.dumps({"key": m["key"], "state": m["state"]}).encode(),
                                         {"Content-Type": "application/json"})
            urllib.request.urlopen(req).read()
    except OSError as e:
        print("Servizio non raggiungibile (%s): cambia un'impostazione dalla dashboard per riapplicarle." % e)


if __name__ == "__main__":
    main()
