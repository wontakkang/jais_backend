from app.utils.protocol.LSIS.continuous_read_byte import Continuous_Read_Request
from app.utils.protocol.LSIS.exceptions import LSIS_IOException, InvalidMessageReceivedException
from app.utils.protocol.LSIS.framer import LSIS_Framer
from app.utils.protocol.LSIS.logger import Log
from app.utils.protocol.LSIS.pdu import LSIS_XGT_Request
import struct
from app.utils.protocol.LSIS.constants import LSIS_XGT_constants
from app.utils.protocol.LSIS.utilities import interpretation


class LSIS_SocketFramer(LSIS_Framer):
    method = "socket"

    def __init__(self, decoder, client=None, address=None):
        super().__init__(decoder, client)
        try:
            self.address = address.getsockname()
        except AttributeError as err:
            self.address = address
            Log.error(f'LSIS_SocketFramer : {address} {err}')
        self._buffer = b""
        self._header = {
            "company_id": 0,
            "PLC_Info": 0,
            "CPU_Info": 0,
            "sorce_of_Frame": 0,
            "invokeID": 0,
            "length": 0,
            "FEnet_Position": 0,
            "BBC": 0,
        }
        self._instruction = {
            "_command": 0,
            "dataType": 0,
            "block": 0,
            "variable_Length": 0,
            "variable": "",
            "address": self.address,
            "dataCount": 0,
            "reserved": 0,
            "error_Status": 0,
        }
        self._registers = []
        self._hsize = 0x13
        self.header = []
        self.instruction = []

    def addToFrame(self, message):
        """Add new packet data to the current frame buffer.

        :param message: The most recent packet
        """
        self._buffer += message

    def isFrameReady(self):
        return len(self._buffer) > self._hsize

    def checkFrame(self):
        """Check and decode the next frame.

        Return true if we were successful.
        """
        try:
            pdu = LSIS_XGT_Request()
            self.header = pdu.decode(self._buffer)
            (
                self._header["company_id"],
                self._header["PLC_Info"],
                self._header["CPU_Info"],
                self._header["sorce_of_Frame"],
                self._header["invokeID"],
                self._header["length"],
                self._header["FEnet_Position"],
                self._header["BBC"],
            ) = self.header
            if LSIS_XGT_constants.companyID_unpack[1] == self._header["company_id"]:
                return True
            else:
                return False
        except:
            return False

    def getFrame(self):
        """Return the next frame from the buffered data.

        :returns: The next full frame buffer
        """
        return self._buffer[20:]

    # ----------------------------------------------------------------------- #
    # Public Member Functions
    # ----------------------------------------------------------------------- #
    def decode_data(self, data):
        """Decode data."""
        try:
            (
                self._header["company_id"],
                self._header["PLC_Info"],
                self._header["CPU_Info"],
                self._header["sorce_of_Frame"],
                self._header["invokeID"],
                self._header["length"],
                self._header["FEnet_Position"],
                self._header["BBC"],
            ) = struct.unpack(self.header[0], data[:20])
            return self._header
        except:
            return {}

    def processIncomingPacket(self, data, callback, **kwargs):
        Log.debug("Processing: {}", data, ":hex")
        self.addToFrame(data)
        try:
            while True:
                if self.isFrameReady():
                    if self.checkFrame():
                        self._process(callback)
                    else:
                        Log.debug("Frame check failed, ignoring!!")
                        self.resetFrame()
                    break
                else:
                    if len(self._buffer):
                        # print("self._buffer: ", self._buffer)
                        # Possible error ???
                        if self._header["length"] < 2:
                            self._process(callback, error=True)
                    break
        except Exception as err:
            Log.debug('socket_framer.py :: LSIS_SocketFramer :: processIncomingPacket Exception :', err)

    def _process(self, callback, error=False):
        """Process incoming packets irrespective error condition."""
        data = self.getRawFrame() if error else self.getFrame()
        try:
            result = self.decoder.decode(data)

            if result is None:
                raise LSIS_IOException("Unable to decode request")
            if result._decode[0] == 89:
                (
                    self._instruction["_command"],
                    self._instruction["dataType"],
                    reversed,
                    self._instruction["error_Status"],
                    self._instruction["block"],
                ) = result._decode
            else:
                (
                    self._instruction["_command"],
                    self._instruction["dataType"],
                    reversed,
                    self._instruction["error_Status"],
                    self._instruction["block"],
                    # self._instruction["variable"],  연속읽기 응답에 변수항목없음
                    self._instruction["dataCount"],
                ) = result._decode[:6]
            # print('socket_framer.py :: LSIS_SocketFramer :: _process worked :', result)
        except Exception as err:
            Log.error('socket_framer.py :: LSIS_SocketFramer :: _process Exception :', err)
        result.values = result._decode[6:]
        self.populateResult(result)
        self.advanceFrame()
        callback(result)  # defer or push to a thread?

    def advanceFrame(self):
        """Skip over the current framed message.

        This allows us to skip over the current message after we have processed
        it or determined that it contains an error. It also has to reset the
        current frame header handle
        """
        self._buffer = b""
        self._header = {
            "company_id": 0,
            "PLC_Info": 0,
            "CPU_Info": 0,
            "sorce_of_Frame": 0,
            "invokeID": 0,
            "length": 0,
            "FEnet_Position": 0,
            "BBC": 0,
        }
        self._instruction = {
            "_command": 0,
            "dataType": 0,
            "block": 0,
            "variable_Length": 0,
            "variable": "",
            "dataCount": 0,
            "reserved": 0,
            "error_Status": 0,
            "address": self.address,
        }
        self._registers = []

    def getRawFrame(self):
        """Return the complete buffer."""
        return self._buffer

    def populateResult(self, result):
        """Populate the result.

        With the transport specific header

        :param result: The response packet
        """
        result.company_id = self._header["company_id"]
        result.PLC_Info = self._header["PLC_Info"]
        result.CPU_Info = self._header["CPU_Info"]
        result.sorce_of_Frame = self._header["sorce_of_Frame"]
        result.transaction_id = self._header["invokeID"]
        result.length = self._header["length"]
        result.FEnet_Position = self._header["FEnet_Position"]
        result._command = self._instruction["_command"]
        result.block = self._instruction["block"]
        result.dataType = self._instruction["dataType"]
        result.variable = self._instruction["variable"]
        result.variable_Length = self._instruction["variable_Length"]
        result.dataCount = self._instruction["dataCount"]
        # result.address = self._instruction["address"]
        result.address = self.client.params.host
        result.detailedStatus = interpretation(self._header, self._instruction)

    def resetFrame(self):
        self._buffer = b""
        self._header = {
            "company_id": 0,
            "PLC_Info": 0,
            "CPU_Info": 0,
            "sorce_of_Frame": 0,
            "invokeID": 0,
            "length": 0,
            "FEnet_Position": 0,
            "BBC": 0,
        }
        self._instruction = {
            "_command": 0,
            "dataType": 0,
            "block": 0,
            "variable_Length": 0,
            "variable": "",
            "address": self.address,
            "dataCount": 0,
            "reserved": 0,
            "error_Status": 0,
        }
        self._registers = []

    def buildPacket(self, message):
        super(message.__class__, message).encode()
        self.header = message.header
        self.instruction = message.instruction
        packet = struct.pack(*message.header) + struct.pack(*message.instruction)
        message.header = [""]
        message.instruction = [""]
        return packet
