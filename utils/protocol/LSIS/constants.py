INTERNAL_ERROR = "PyLSIS_ internal error"


class Defaults:
    companyID = ["10s", b"LSIS-XGT"]
    companyID_unpack = ["10s", b"LSIS-XGT\x00\x00"]
    InvokeID = ["H", 0]
    Request_Sorce_Of_Frame = ["B", 0x33]  # Sorce_of_Frame: 클라이언트 -> 서버 33 서버에서 클라이언트 11
    System_Sorce_Of_Frame = ["B", 0x22]  # Sorce_of_Frame: 클라이언트 -> 서버 33 서버에서 클라이언트 11
    response_Sorce_Of_Frame = [
        "B",
        0x11,
    ]  # Sorce_of_Frame: 클라이언트 -> 서버 33 서버에서 클라이언트 11
    CPU_Info = ["B", 0]  # CPU_Info: A4 XGK/XGI 시리즈임을판단
    PLC_Info = ["H", 0x00]  # PLC_Info: 클라이언트 -> 서버는 무시(0x00)
    PLC_Info = ["H", 0x00]  # PLC_Info: 클라이언트 -> 서버는 무시(0x00)
    FEnet_Position = ["B", 0]
    SystemCommandRequest = ["H", 0xef]
    ContinuousReadRequest = ["H", 0x54]
    ContinuousReadRecv = ["H", 0x55]
    ContinuousWriteRequest = ["H", 0x58]
    ContinuousWriteRecv = ["H", 0x59]
    ContinuousDataType = ["H", 0x14]
    ContinuousDataType = ["H", 0x14]
    SystemCommandDataType = ["H", 0x0e00]
    SingleDataType = {
        'bit':["H", 0x00],
        'byte':["H", 0x01],
        'word':["H", 0x02],
        'dword':["H", 0x03],
        'lword':["H", 0x04],
    }
    TcpPort = 2004
    TlsPort = 802
    UdpPort = 2002
    Backoff = 0.3
    CloseCommOnError = False
    HandleLocalEcho = False
    Retries = 3
    RetryOnEmpty = False
    RetryOnInvalid = False
    Timeout = 5
    Reconnects = 0
    Strict = True
    Slave: int = 0x00
    Baudrate = 9600
    Parity = "N"
    Bytesize = 8
    Stopbits = 1
    ZeroMode = False
    IgnoreMissingSlaves = False
    ReadSize = 1024
    BroadcastEnable = False
    ReconnectDelay = 100
    ReconnectDelayMax = 1000 * 60 * 5
    Count = 1

LSIS_XGT_constants = Defaults()