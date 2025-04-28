"""Pymodbus: Modbus Protocol Implementation.

Released under the the BSD license
"""

from .logger import lsis_apply_logging_config
from .client.tcp import LSIS_TcpClient
# --------------------------------------------------------------------------- #
# Exported symbols
# --------------------------------------------------------------------------- #

__all__ = [
    "lsis_apply_logging_config",
    "__version__",
    "__version_full__",
    "LSIS_TcpClient",
]
