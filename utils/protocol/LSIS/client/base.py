"""Base for all clients."""
from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass
from typing import Any, Tuple, Type

from .mixin import LSIS_ClientMixin
from ..constants import Defaults
from ..exceptions import ConnectionException, NotImplementedException
from ..factory import ClientDecoder
from ..framer import LSIS_Framer
from ..logger import Log
from ..pdu import LSIS_XGT_Request, LSIS_XGT_Response
from ..transaction import DictTransactionManager
from ..utilities import LSIS_TransactionState


class LSIS_BaseClient(LSIS_ClientMixin):
    """
    **LSIS_BaseClient**

    **모든 클라이언트에서 공통으로 사용하는 매개변수**:

    :param framer: (선택 사항) LSIS 프레이머 클래스.
    :param timeout: (선택 사항) 요청의 타임아웃(초 단위).
    :param retries: (선택 사항) 요청당 최대 재시도 횟수.
    :param retry_on_empty: (선택 사항) 응답이 비어 있을 때 재시도 여부.
    :param close_comm_on_error: (선택 사항) 오류 발생 시 연결 종료 여부.
    :param strict: (선택 사항) 요청 간 1.5 문자 시간의 엄격한 패킷 타이밍 설정.
    :param broadcast_enable: (선택 사항) ID 0을 브로드캐스트 주소로 처리하려면 True로 설정.
    :param reconnect_delay: (선택 사항) 재연결 전 최소 지연 시간(밀리초 단위).
    :param reconnect_delay_max: (선택 사항) 재연결 전 최대 지연 시간(밀리초 단위).
    :param kwargs: (선택 사항) 실험적 매개변수.

    .. tip::
        모든 클라이언트에 공통적인 매개변수와 외부 메서드는 여기에서 문서화되며,
        각 클라이언트에서 반복되지 않습니다.

    .. tip::
        **delay_ms**는 연결이 실패할 때마다 자동으로 두 배 증가하며,
        **reconnect_delay**에서 **reconnect_delay_max**까지 증가합니다.
        자동 재연결을 방지하려면 `reconnect_delay=0`으로 설정하세요.

    :mod:`LSISBaseClient`는 일반적으로 :mod:`pymodbus` 외부에서 참조되지 않으며,
    사용자가 커스텀 클라이언트를 만들고자 할 경우에만 사용됩니다.

    커스텀 클라이언트 클래스는 **반드시** :mod:`LSISBaseClient`를 상속해야 합니다. 예시::


        class myOwnClient(LSISBaseClient):

            def __init__(self, **kwargs):
                super().__init__(kwargs)

        def run():
            client = myOwnClient(...)
            client.connect()
            rr = client.read_coils(0x01)
            client.close()

    **모든 클라이언트에 공통적인 애플리케이션 메서드**:
    """

    @dataclass
    class _params:  # pylint: disable=too-many-instance-attributes
        """Parameter class."""

        host: str = None
        port: str | int = None
        framer: Type[LSIS_Framer] = None
        timeout: float = None
        retries: int = None
        retry_on_empty: bool = None
        close_comm_on_error: bool = None
        strict: bool = None
        broadcast_enable: bool = None
        kwargs: dict = None
        reconnect_delay: int = None
        reconnect_delay_max: int = None

        baudrate: int = None
        bytesize: int = None
        parity: str = None
        stopbits: int = None
        handle_local_echo: bool = None

        source_address: Tuple[str, int] = None

        sslctx: str = None
        certfile: str = None
        keyfile: str = None
        password: str = None
        server_hostname: str = None

    def __init__(
        self,
        framer: Type[LSIS_Framer] = None,
        timeout: str | float = Defaults.Timeout,
        retries: str | int = Defaults.Retries,
        retry_on_empty: bool = Defaults.RetryOnEmpty,
        close_comm_on_error: bool = Defaults.CloseCommOnError,
        strict: bool = Defaults.Strict,
        broadcast_enable: bool = Defaults.BroadcastEnable,
        reconnect_delay: int = Defaults.ReconnectDelay,
        reconnect_delay_max: int = Defaults.ReconnectDelayMax,
        **kwargs: Any,
    ) -> None:
        """Initialize a client instance."""
        self.params = self._params()
        self.params.framer = framer
        self.params.timeout = float(timeout)
        self.params.retries = int(retries)
        self.params.retry_on_empty = bool(retry_on_empty)
        self.params.close_comm_on_error = bool(close_comm_on_error)
        self.params.strict = bool(strict)
        self.params.broadcast_enable = bool(broadcast_enable)
        self.params.reconnect_delay = int(reconnect_delay)
        self.params.reconnect_delay_max = int(reconnect_delay_max)
        self.params.kwargs = kwargs

        # Common variables.
        self.framer = self.params.framer(ClientDecoder(), self)
        self.transaction = DictTransactionManager(
            self, retries=retries, retry_on_empty=retry_on_empty, **kwargs
        )
        self.delay_ms = self.params.reconnect_delay
        self.use_protocol = False
        self._connected = False
        self.use_udp = False
        self.state = LSIS_TransactionState.IDLE
        self.last_frame_end: float = 0
        self.silent_interval: float = 0
        self.transport = None

        # Initialize  mixin
        super().__init__()

    # ----------------------------------------------------------------------- #
    # Client external interface
    # ----------------------------------------------------------------------- #
    def register(self, custom_response_class: LSIS_XGT_Response) -> None:
        """Register a custom response class with the decoder (call **sync**).

        :param custom_response_class: (optional) Modbus response class.
        :raises MessageRegisterException: Check exception text.

        Use register() to add non-standard responses (like e.g. a login prompt) and
        have them interpreted automatically.
        """
        self.framer.decoder.register(custom_response_class)

    def connect(self):
        """Connect to the modbus remote host (call **sync/async**).

        :raises ModbusException: Different exceptions, check exception text.

        **Remark** Retries are handled automatically after first successful connect.
        """
        raise NotImplementedException

    def is_socket_open(self) -> bool:
        """Return whether socket/serial is open or not (call **sync**)."""
        raise NotImplementedException

    def idle_time(self) -> float:
        """Time before initiating next transaction (call **sync**).

        Applications can call message functions without checking idle_time(),
        this is done automatically.
        """
        if self.last_frame_end is None or self.silent_interval is None:
            return 0
        return self.last_frame_end + self.silent_interval

    def reset_delay(self) -> None:
        """Reset wait time before next reconnect to minimal period (call **sync**)."""
        self.delay_ms = self.params.reconnect_delay

    def execute(self, request: LSIS_XGT_Request = None) -> LSIS_XGT_Response:
        """Execute request and get response (call **sync/async**).

        :param request: The request to process
        :returns: The result of the request execution
        :raises ConnectionException: Check exception text.
        """
        if self.use_protocol:
            if not self._connected:
                raise ConnectionException(f"Not connected[{str(self)}]")
            return self.async_execute(request)
        if not self.connect():
            raise ConnectionException(f"Failed to connect[{str(self)}]")
        return self.transaction.execute(request)

    def close(self) -> None:
        """Close the underlying socket connection (call **sync/async**)."""
        raise NotImplementedException

    # ----------------------------------------------------------------------- #
    # Merged client methods
    # ----------------------------------------------------------------------- #
    def client_made_connection(self, protocol):
        """Run transport specific connection."""

    def client_lost_connection(self, protocol):
        """Run transport specific connection lost."""

    def datagram_received(self, data, _addr):
        """Receive datagram."""
        self.data_received(data)

    async def async_execute(self, request=None):
        """Execute requests asynchronously."""
        request.transaction_id = self.transaction.getNextTID()
        packet = self.framer.buildPacket(request)
        Log.debug("send: {}", packet, ":hex")
        if self.use_udp:
            self.transport.sendto(packet)
        else:
            self.transport.write(packet)
        req = self._build_response(request.transaction_id)
        if self.params.broadcast_enable and not request.unit_id:
            resp = b"Broadcast write sent - no response expected"
        else:
            try:
                resp = await asyncio.wait_for(req, timeout=self.params.timeout)
            except asyncio.exceptions.TimeoutError:
                self.connection_lost("trying to send")
                raise
        return resp

    def connection_made(self, transport):
        """Call when a connection is made.

        The transport argument is the transport representing the connection.
        """
        self.transport = transport
        Log.debug("Client connected to modbus server")
        self._connected = True
        self.client_made_connection(self)

    def connection_lost(self, reason):
        """Call when the connection is lost or closed.

        The argument is either an exception object or None
        """
        if self.transport:
            self.transport.abort()
            if hasattr(self.transport, "_sock"):
                self.transport._sock.close()  # pylint: disable=protected-access
            self.transport = None
        self.client_lost_connection(self)
        Log.debug("Client disconnected from modbus server: {}", reason)
        self._connected = False
        for tid in list(self.transaction):
            self.raise_future(
                self.transaction.getTransaction(tid),
                ConnectionException("Connection lost during request"),
            )

    def data_received(self, data):
        """Call when some data is received.

        data is a non-empty bytes object containing the incoming data.
        """
        Log.debug("recv: {}", data, ":hex")
        self.framer.processIncomingPacket(data, self._handle_response, unit=0)

    def create_future(self):
        """Help function to create asyncio Future object."""
        return asyncio.Future()

    def raise_future(self, my_future, exc):
        """Set exception of a future if not done."""
        if not my_future.done():
            my_future.set_exception(exc)

    def _handle_response(self, reply, **_kwargs):
        """Handle the processed response and link to correct deferred."""
        if reply is not None:
            tid = reply.transaction_id
            if handler := self.transaction.getTransaction(tid):
                if not handler.done():
                    handler.set_result(reply)
            else:
                Log.debug("Unrequested message: {}", reply, ":str")

    def _build_response(self, tid):
        """Return a deferred response for the current request."""
        my_future = self.create_future()
        if not self._connected:
            self.raise_future(my_future, ConnectionException("Client is not connected"))
        else:
            self.transaction.addTransaction(my_future, tid)
        return my_future

    @property
    def async_connected(self):
        """Return connection status."""
        return self._connected

    async def async_close(self):
        """Close connection."""
        if self.transport:
            self.transport.close()
        self._connected = False

    # ----------------------------------------------------------------------- #
    # Internal methods
    # ----------------------------------------------------------------------- #
    def send(self, request):
        """Send request.

        :meta private:
        """
        if self.state != LSIS_TransactionState.RETRYING:
            Log.debug('New Transaction state "SENDING"')
            self.state = LSIS_TransactionState.SENDING
        return request

    def recv(self, size):
        """Receive data.

        :meta private:
        """
        return size

    @classmethod
    def _get_address_family(cls, address):
        """Get the correct address family."""
        try:
            _ = socket.inet_pton(socket.AF_INET6, address)
        except socket.error:  # not a valid ipv6 address
            return socket.AF_INET
        return socket.AF_INET6

    # ----------------------------------------------------------------------- #
    # The magic methods
    # ----------------------------------------------------------------------- #
    def __enter__(self):
        """Implement the client with enter block.

        :returns: The current instance of the client
        :raises ConnectionException:
        """

        if not self.connect():
            raise ConnectionException(f"Failed to connect[{self.__str__()}]")
        return self

    async def __aenter__(self):
        """Implement the client with enter block.

        :returns: The current instance of the client
        :raises ConnectionException:
        """
        if not await self.connect():
            raise ConnectionException(f"Failed to connect[{self.__str__()}]")
        return self

    def __exit__(self, klass, value, traceback):
        """Implement the client with exit block."""
        self.close()

    async def __aexit__(self, klass, value, traceback):
        """Implement the client with exit block."""
        await self.close()

    def __str__(self):
        """Build a string representation of the connection.

        :returns: The string representation
        """
        return f"{self.__class__.__name__} {self.params.host}:{self.params.port}"
