"""LSIS_ Client Common."""
import struct
from enum import Enum
from typing import Any, List, Tuple, Union

from .. import continuous_read_byte as pdu_con_read
from .. import continuous_write_byte as pdu_con_write
from .. import single_write_byte as pdu_sin_write
from ..constants import INTERNAL_ERROR
from ..exceptions import LSIS_Exception
from ..pdu import LSIS_XGT_Request, LSIS_XGT_Response
from ..logger import Log


class LSIS_ClientMixin:  # pylint: disable=too-many-public-methods
    def __init__(self):
        """Initialize."""

    def execute(self, request: LSIS_XGT_Request) -> LSIS_XGT_Response:
        raise LSIS_Exception(INTERNAL_ERROR)

    def continuous_read_bytes(
        self, address: str, count: int = 1, **kwargs: Any
    ) -> LSIS_XGT_Response:
        Log.debug("continuous_read_bytes {}, {}", address, count)
        return self.execute(
            pdu_con_read.Continuous_Read_Request(address, count, **kwargs)
        )

    def continuous_write_bytes(
        self, address: str, count: int = 1, values: list = [], **kwargs: Any
    ) -> LSIS_XGT_Response:
        Log.debug("continuous_write_bytes {}, {}, {}", address, count, values)
        return self.execute(
            pdu_con_write.Continuous_Write_Request(address, count, values, **kwargs)
        )

    def single_write_datas(
        self, data_type: str, block_cnt: int = 1, blockArray: list = [], **kwargs: Any
    ) -> LSIS_XGT_Response:
        Log.debug("continuous_write_bytes {}, {}, {}", data_type, block_cnt, blockArray)
        return self.execute(
            pdu_sin_write.Single_Write_Request(data_type, block_cnt, blockArray, **kwargs)
        )
    # ------------------
    # Converter methods
    # ------------------

    class DATATYPE(Enum):
        """Datatype enum for convert_* calls."""

        INT16 = ("h", 1)
        UINT16 = ("H", 1)
        INT32 = ("i", 2)
        UINT32 = ("I", 2)
        INT64 = ("q", 4)
        UINT64 = ("Q", 4)
        FLOAT32 = ("f", 2)
        FLOAT64 = ("d", 4)
        STRING = ("s", 0)

    @classmethod
    def convert_from_registers(
        cls, registers: List[int], data_type: DATATYPE
    ) -> Union[int, float, str]:
        """Convert registers to int/float/str.

        :param registers: list of registers received from e.g. read_holding_registers()
        :param data_type: data type to convert to
        :returns: int, float or str depending on "to_type"
        :raises ModbusException: when size of registers is not 1, 2 or 4
        """
        byte_list = bytearray()
        for x in registers:
            byte_list.extend(int.to_bytes(x, 2, "big"))
        if data_type == cls.DATATYPE.STRING:
            if byte_list[-1:] == b"\00":
                byte_list = byte_list[:-1]
            return byte_list.decode("utf-8")
        if len(registers) != data_type.value[1]:
            raise LSIS_Exception(
                f"Illegal size ({len(registers)}) of register array, cannot convert!"
            )
        return struct.unpack(f">{data_type.value[0]}", byte_list)[0]

    @classmethod
    def convert_to_registers(
        cls, value: Union[int, float, str], data_type: DATATYPE
    ) -> List[int]:
        """Convert int/float/str to registers (16/32/64 bit).

        :param value: value to be converted:
        :param data_type: data type to convert to
        :returns: List of registers, can be used directly in e.g. write_registers()
        """
        if data_type == cls.DATATYPE.STRING:
            byte_list = value.encode()  # type: ignore[union-attr]
            if len(byte_list) % 2:
                byte_list += b"\x00"
        else:
            byte_list = struct.pack(f">{data_type.value[0]}", value)
        regs = [
            int.from_bytes(byte_list[x : x + 2], "big")
            for x in range(0, len(byte_list), 2)
        ]
        return regs
