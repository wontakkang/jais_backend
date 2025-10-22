import importlib

def _list_serial_ports():
    """사용 가능한 시리얼 포트에 대한 (장치, 라벨) 튜플 목록을 반환합니다.
    non-pyserial 패키지와의 충돌을 피하기 위해 serial.tools.list_ports를 안전하게 임포트하려고 시도합니다.
    """
    ports = []
    try:
        # 일반적인 임포트 시도
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