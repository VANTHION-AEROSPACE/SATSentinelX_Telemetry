import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from receiver import open_serial_port


class FakePort:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.events = []
        self._port = None
        self._dtr = None
        self._rts = None

    @property
    def port(self):
        return self._port

    @port.setter
    def port(self, value):
        self._port = value
        self.events.append(("port", value))

    @property
    def dtr(self):
        return self._dtr

    @dtr.setter
    def dtr(self, value):
        self._dtr = value
        self.events.append(("dtr", value))

    @property
    def rts(self):
        return self._rts

    @rts.setter
    def rts(self, value):
        self._rts = value
        self.events.append(("rts", value))

    def open(self):
        self.events.append(("open",))


class FakeSerialModule:
    def __init__(self):
        self.instance = None

    def Serial(self, **kwargs):
        self.instance = FakePort(**kwargs)
        return self.instance


class SerialOpenTests(unittest.TestCase):
    def test_dtr_rts_are_low_before_open(self):
        module = FakeSerialModule()
        port = open_serial_port(module, "COM7", 115200)

        self.assertIs(port, module.instance)
        self.assertEqual(port.kwargs, {
            "port": None, "baudrate": 115200, "timeout": 1
        })
        self.assertEqual(port.events, [
            ("port", "COM7"), ("dtr", False), ("rts", False), ("open",)
        ])


if __name__ == "__main__":
    unittest.main()
