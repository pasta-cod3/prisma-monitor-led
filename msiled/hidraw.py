import fcntl
import glob
import os
import select
import time

WRITE_GAP = 0.004


def _ioc_feature(nr, length):
    return (3 << 30) | (length << 16) | (ord("H") << 8) | nr


def _read_attr(path, name):
    try:
        with open(os.path.join(path, name)) as f:
            return f.read().strip()
    except OSError:
        return None


class Node:

    def __init__(self, sys_path):
        self.name = os.path.basename(sys_path)
        self.dev = "/dev/" + self.name
        hid_dir = os.path.realpath(os.path.join(sys_path, "device"))
        iface_dir = os.path.dirname(hid_dir)
        self.usb_dir = os.path.dirname(iface_dir)
        self.vid = int(_read_attr(self.usb_dir, "idVendor") or "0", 16)
        self.pid = int(_read_attr(self.usb_dir, "idProduct") or "0", 16)
        self.interface = int(_read_attr(iface_dir, "bInterfaceNumber") or "99", 16)
        self.serial = _read_attr(self.usb_dir, "serial")
        self.port = os.path.basename(self.usb_dir)
        self.hub = self.port.rsplit(".", 1)[0] if "." in self.port else None

    def __repr__(self):
        return "<%s %04x:%04x if%d %s>" % (self.dev, self.vid, self.pid, self.interface, self.port)


def nodes():
    found = []
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            found.append(Node(path))
        except OSError:
            continue
    return found


class Device:
    def __init__(self, path):
        self.path = path
        self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)

    def close(self):
        os.close(self.fd)

    def send_feature(self, buf):
        fcntl.ioctl(self.fd, _ioc_feature(0x06, len(buf)), bytes(buf))
        time.sleep(WRITE_GAP)

    def get_feature(self, report_id, length):
        buf = bytearray(length)
        buf[0] = report_id
        n = fcntl.ioctl(self.fd, _ioc_feature(0x07, length), buf)
        return bytes(buf[:n]) if isinstance(n, int) and n > 0 else bytes(buf)

    def write(self, buf):
        os.write(self.fd, bytes(buf))
        time.sleep(WRITE_GAP)

    def drain(self):
        while select.select([self.fd], [], [], 0)[0]:
            try:
                os.read(self.fd, 64)
            except BlockingIOError:
                break

    def read(self, length=64, timeout=1.0):
        if not select.select([self.fd], [], [], timeout)[0]:
            return None
        try:
            return os.read(self.fd, length)
        except BlockingIOError:
            return None
