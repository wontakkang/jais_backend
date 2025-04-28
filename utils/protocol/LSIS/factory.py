import struct

from .exceptions import LSIS_Exception
from .logger import Log
from .continuous_read_byte import (
    Continuous_Read_Request,
    Continuous_Read_Response,
)
from .constants import LSIS_XGT_constants

from .continuous_write_byte import (
    Continuous_Write_Request,
    Continuous_Write_Response,
)

from .single_write_byte import (
    Single_Write_Request,
    Single_Write_Response,
)

# --------------------------------------------------------------------------- #
# Server Decoder
# --------------------------------------------------------------------------- #
class ServerDecoder:
    """Request Message Factory (Server).

    To add more implemented functions, simply add them to the list
    """

    __function_table = [
        Continuous_Read_Request,
        Continuous_Read_Response,
        Continuous_Write_Request,
        Continuous_Write_Response,
        Single_Write_Request,
        Single_Write_Response,
    ]
    __sub_function_table = []

    @classmethod
    def getFCdict(cls):
        """Build function code - class list."""
        return {f.command[1]: f for f in cls.__function_table}

    def __init__(self):
        """Initialize the client lookup tables."""
        functions = {f.command[1] for f in self.__function_table}
        self.__lookup = self.getFCdict()
        self.__sub_lookup = {f: {} for f in functions}
        for f in self.__sub_function_table:
            self.__sub_lookup[f.command[1]][f.command[1]] = f

    def decode(self, message):
        try:
            return self._helper(message)
        except LSIS_Exception as exc:
            Log.warning("Unable to decode request {}", exc)
        return None

    def lookupPduClass(self, function_code):
        """Use `function_code` to determine the class of the PDU.

        :param function_code: The function code specified in a frame.
        :returns: The class of the PDU that has a matching `function_code`.
        """
        return self.__lookup.get(function_code)

    def _helper(self, data):
        fc_string = command = struct.unpack("<H", data[:2])[0]
        if command in self.__lookup:
            fc_string = "%s: %s" % (  # pylint: disable=consider-using-f-string
                str(self.__lookup[command])  # pylint: disable=use-maxsplit-arg
                .split(".")[-1]
                .rstrip('">"'),
                command,
            )
        Log.debug("Factory Response[{}]", fc_string)
        try:
            code = struct.unpack("<HB", data[6:9])
            request = self.__lookup.get(command, lambda values: 0)
        except:
            request = None
        if code[0] == 65535:
            Log.debug("Exception Code[{}]", hex(code[1]))
            raise LSIS_Exception(f"Unknown response {hex(code[1])}")
        if not request:
            raise LSIS_Exception(f"Unknown response")
        if len(data) > 0:
            request._decode = request.decode(request, data)
        return request

    def register(self, function=None):
        print("ServerDecoder register")


# --------------------------------------------------------------------------- #
# Client Decoder
# --------------------------------------------------------------------------- #
class ClientDecoder:
    """Response Message Factory (Client).

    To add more implemented functions, simply add them to the list
    """

    function_table = [
        Continuous_Read_Request,
        Continuous_Read_Response,
        Continuous_Write_Request,
        Continuous_Write_Response,
        Single_Write_Request,
        Single_Write_Response,
    ]
    __sub_function_table = []


    def __init__(self):
        functions = {}
        """Initialize the client lookup tables."""
        try:
            functions = {f.command[1] for f in self.function_table}
            self.__lookup = {f.command[1]: f for f in self.function_table}
            self.__sub_lookup = {f: {} for f in functions}
            for f in self.__sub_function_table:
                self.__sub_lookup[f.command[1]][f.command[1]] = f
        except Exception as err:
            print('factory.py :: ClientDecoder : ', err)

    def lookupPduClass(self, command):
        """Use `function_code` to determine the class of the PDU.

        :param function_code: The function code specified in a frame.
        :returns: The class of the PDU that has a matching `function_code`.
        """
        return self.__lookup.get(command)

    def decode(self, message):
        return self._helper(message)
        try:
            return self._helper(message)
        except LSIS_Exception as exc:
            Log.error("Unable to decode response {}", exc)
        except Exception as exc:  # pylint: disable=broad-except
            Log.error("General exception: {}", exc)
        return None

    def _helper(self, data):
        fc_string = command = struct.unpack("<H", data[:2])[0]
        if command in self.__lookup:
            fc_string = "%s: %s" % (  # pylint: disable=consider-using-f-string
                str(self.__lookup[command])  # pylint: disable=use-maxsplit-arg
                .split(".")[-1]
                .rstrip('">"'),
                command,
            )
        Log.debug("Factory Response[{}]", fc_string)
        try:
            code = struct.unpack("<HB", data[6:9])
            response = self.__lookup.get(command, lambda values: [])
        except:
            response = None
        if code[0] == 65535:
            Log.debug("Exception Code[{}]", hex(code[1]))
            raise LSIS_Exception(f"Unknown response {hex(code[1])}")
        if not response:
            raise LSIS_Exception(f"Unknown response")
        if len(data) > 0:
            response._decode = response.decode(response, data)
        return response


# --------------------------------------------------------------------------- #
# Exported symbols
# --------------------------------------------------------------------------- #


__all__ = ["ServerDecoder", "ClientDecoder"]
