import argparse

from . import edid, models


def main():
    p = argparse.ArgumentParser(prog="python3 -m msiled", description="LED dei monitor MSI")
    p.add_argument("--detect", action="store_true", help="mostra i monitor MSI trovati e il loro supporto LED")
    p.add_argument("--list-models", action="store_true", help="elenca i modelli conosciuti")
    p.add_argument("--color", help="imposta un colore fisso, es. ff0000 (primo monitor trovato)")
    p.add_argument("--zone", help="zona da colorare (predefinito: tutte)")
    p.add_argument("--brightness", type=int, default=100, help="0-100")
    a = p.parse_args()

    if a.list_models:
        for m in models.MODELS:
            print("%-14s %-12s %s" % (m["id"], m["backend"] + ("/" + m["variant"] if m["variant"] else ""),
                                      "provato" if m["tested"] else "non ancora provato"))
        return
    devices, notes = models.Detector().scan()
    if a.detect or not a.color:
        print("Monitor collegati (video):", ", ".join("%s %s" % (m["connector"], m["name"] or m["vendor"])
                                                       for m in edid.monitors()) or "nessuno")
        for d in devices:
            m = d["model"]
            print("- %s via %s (%s)%s" % (m["name"], d["path"], d["backend"], "" if m["tested"] else " [non ancora provato]"))
            for z in m["zones"]:
                print("    %-4s %-18s %3d LED%s" % (z["id"], z["label"], z["leds"], " (per LED)" if z["id"] in m["per_led"] else ""))
        for n in notes:
            print("! " + models.note_text(n))
        if not devices:
            print("Nessun monitor MSI con LED trovato via USB.")
        return
    if not devices:
        raise SystemExit("Nessun monitor MSI con LED trovato via USB.")
    d = devices[0]
    zones = [z["id"] for z in d["model"]["zones"] if not a.zone or z["id"] == a.zone]
    state = {"brightness": a.brightness,
             "zones": {z["id"]: {"effect": "static" if z["id"] in zones else "off", "colors": ["#" + a.color.lstrip("#")],
                                 "speed": 20} for z in d["model"]["zones"]}}
    backend = models.open_backend(d)
    try:
        backend.apply(state)
    finally:
        backend.close()


if __name__ == "__main__":
    main()
