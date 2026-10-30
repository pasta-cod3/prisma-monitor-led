RAINBOW = ["#ff0000", "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#ff00ff"]


def hex_to_rgb(s):
    s = s.lstrip("#")
    if len(s) != 6:
        raise ValueError("colore non valido: #%s" % s)
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def pad(colors, n):
    return [colors[min(i, len(colors) - 1)] for i in range(n)]
