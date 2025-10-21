
import importlib

def _list_serial_ports():
    """Return list of (device, label) tuples for available serial ports.
    Tries to import serial.tools.list_ports robustly to avoid conflicts with non-pyserial packages.
    """
    ports = []
    try:
        # try common import
        from serial.tools import list_ports
        comps = list_ports.comports()
        return [(p.device, f"{p.device} - {p.description}") for p in comps]
    except Exception:
        pass
    try:
        mod = importlib.import_module('serial.tools.list_ports')
        comps = mod.comports()
        return [(p.device, f"{p.device} - {p.description}") for p in comps]
    except Exception:
        pass
    try:
        import serial
        tools = getattr(serial, 'tools', None)
        if tools is not None and hasattr(tools, 'list_ports'):
            comps = tools.list_ports.comports()
            return [(p.device, f"{p.device} - {p.description}") for p in comps]
    except Exception:
        pass
    return ports