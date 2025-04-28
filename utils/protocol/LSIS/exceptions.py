"""Pymodbus Exceptions.

Custom exceptions to be used in the Modbus code.
"""


class LSIS_Exception(Exception):
    """Base LSIS_ exception."""

    def __init__(self, string):
        """Initialize the exception.

        :param string: The message to append to the error
        """
        self.string = string
        super().__init__()

    def __str__(self):
        """Return string representation."""
        return f"LSIS_ Error: {self.string}"

    def isError(self):
        """Error"""
        return True


class NoSuchSlaveException(LSIS_Exception):
    """Error resulting from making a request to a slave that does not exist."""

    def __init__(self, string=""):
        """Initialize the exception.

        :param string: The message to append to the error
        """
        message = f"[No Such Slave] {string}"
        LSIS_Exception.__init__(self, message)

class LSIS_IOException(LSIS_Exception):
    """Error resulting from data i/o."""

    def __init__(self, string="", function_code=None):
        """Initialize the exception.

        :param string: The message to append to the error
        """
        self.fcode = function_code
        self.message = f"[Input/Output] {string}"
        LSIS_Exception.__init__(self, self.message)


class ParameterException(LSIS_Exception):
    """Error resulting from invalid parameter."""

    def __init__(self, string=""):
        """Initialize the exception.

        :param string: The message to append to the error
        """
        message = f"[Invalid Parameter] {string}"
        LSIS_Exception.__init__(self, message)


class NoSuchSlaveException(LSIS_Exception):
    """Error resulting from making a request to a slave that does not exist."""

    def __init__(self, string=""):
        """Initialize the exception.

        :param string: The message to append to the error
        """
        message = f"[No Such Slave] {string}"
        LSIS_Exception.__init__(self, message)


class NotImplementedException(LSIS_Exception):
    """Error resulting from not implemented function."""

    def __init__(self, string=""):
        """Initialize the exception.

        :param string: The message to append to the error
        """
        message = f"[Not Implemented] {string}"
        LSIS_Exception.__init__(self, message)


class ConnectionException(LSIS_Exception):
    """Error resulting from a bad connection."""

    def __init__(self, string=""):
        """Initialize the exception.

        :param string: The message to append to the error
        """
        message = f"[Connection] {string}"
        LSIS_Exception.__init__(self, message)


class InvalidMessageReceivedException(LSIS_Exception):
    """Error resulting from invalid response received or decoded."""

    def __init__(self, string=""):
        """Initialize the exception.

        :param string: The message to append to the error
        """
        message = f"[Invalid Message] {string}"
        LSIS_Exception.__init__(self, message)


class MessageRegisterException(LSIS_Exception):
    """Error resulting from failing to register a custom message request/response."""

    def __init__(self, string=""):
        """Initialize."""
        message = f"[Error registering message] {string}"
        LSIS_Exception.__init__(self, message)


# --------------------------------------------------------------------------- #
# Exported symbols
# --------------------------------------------------------------------------- #
__all__ = [
    "LSIS_Exception",
    "LSIS_IOException",
    "ParameterException",
    "NotImplementedException",
    "ConnectionException",
    "NoSuchSlaveException",
    "InvalidMessageReceivedException",
    "MessageRegisterException",
]
