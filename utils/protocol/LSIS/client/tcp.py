"""LSIS_ client async TCP communication."""
import asyncio
import select
import socket
import time
from typing import Any, Tuple, Type

from ..client.base import LSIS_BaseClient
from ..constants import Defaults
from ..exceptions import ConnectionException
from ..framer import LSIS_Framer
from ..framer.socket_framer import LSIS_SocketFramer
from ..logger import Log
from ..utilities import LSIS_TransactionState


class LSIS_TcpClient(LSIS_BaseClient):
    protocol_code = 2
    """
    **LSIS_TcpClient**

    :param host: 호스트 IP 주소 또는 호스트 이름
    :param port: (선택 사항) 통신에 사용되는 포트
    :param framer: (선택 사항) 프레이머 클래스
    :param source_address: (선택 사항) 클라이언트의 소스 주소
    :param kwargs: (선택 사항) 실험적 매개변수

    유닉스 도메인 소켓을 사용하려면 `host="unix:<path>"`로 설정하면 됩니다.

    예제::

        from pymodbus.client import LSIS_TcpClient

        async def run():
            client = LSIS_TcpClient("localhost")

            client.connect()
            ...
            client.close()

    참고: `AsyncLSIS_TcpClient`와는 달리 자동 재연결 기능이 없습니다.
    """

    def __init__(
        self,
        host: str,
        port: int = Defaults.TcpPort,
        framer: Type[LSIS_Framer] = LSIS_SocketFramer,
        source_address: Tuple[str, int] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(framer=framer, **kwargs)
        """Initialize LSIS_ TCP Client."""
        self.params.host = host
        self.params.port = port
        self.params.source_address = source_address
        self.socket = None
        kwargs.pop("test", 0x00)
        Log.debug(f'tcp.py :: Initialize LSIS_ TCP Client : ', self.params)

    @property
    def connected(self):
        """Connect internal."""
        return self.connect()

    def connect(self, retry_forever: bool = False):
        """
        서버에 동기적으로 연결.
        :param retry_forever: True로 설정하면 연결이 성공할 때까지 무한 재시도.
        :return: 연결 성공 여부.
        """
        attempt = 0
        while True:
            try:
                if self.socket:
                    return True

                if self.params.host.startswith("unix:"):
                    self.socket = socket.socket(socket.AF_UNIX)
                    self.socket.settimeout(self.params.timeout)
                    self.socket.connect(self.params.host[5:])
                else:
                    self.socket = socket.create_connection(
                        (self.params.host, self.params.port),
                        timeout=self.params.timeout,
                        source_address=self.params.source_address,
                    )
                Log.debug(
                    f"Connection to LSIS server established. Socket {self.params.host, self.params.port}."
                )
                return True
            except socket.error as e:
                Log.error(
                    f"Connection to {self.params.host}:{self.params.port} failed: {e}"
                )
                self.close()

                # 무한 재시도가 설정되지 않은 경우
                if not retry_forever:
                    raise ConnectionException(
                        f"Failed to connect to {self.params.host}:{self.params.port}"
                    )

                # 재시도 간 대기 시간 계산
                attempt += 1
                delay = min(
                    self.params.reconnect_delay * (2 ** (attempt - 1)),
                    self.params.reconnect_delay_max,
                )
                Log.warning(f"Retrying connection in {delay / 1000} seconds...")
                time.sleep(delay / 1000)

    def close(self):
        """Close the underlying socket connection."""
        if self.socket:
            self.socket.close()
        self.socket = None

    def _check_read_buffer(self):
        """Check read buffer."""
        time_ = time.time()
        end = time_ + self.params.timeout
        data = None
        ready = select.select([self.socket], [], [], end - time_)
        if ready[0]:
            data = self.socket.recv(1024)
        return data

    def send(self, request):
        """Send data on the underlying socket."""
        super().send(request)
        if not self.socket:
            raise ConnectionException(str(self))
        if self.state == LSIS_TransactionState.RETRYING:
            if data := self._check_read_buffer():
                return data

        if request:
            return self.socket.send(request)
        return 0

    def recv(self, size):
        """Read data from the underlying descriptor."""
        super().recv(size)
        if not self.socket:
            raise ConnectionException(str(self))

        # socket.recv(size) waits until it gets some data from the host but
        # not necessarily the entire response that can be fragmented in
        # many packets.
        # To avoid split responses to be recognized as invalid
        # messages and to be discarded, loops socket.recv until full data
        # is received or timeout is expired.
        # If timeout expires returns the read data, also if its length is
        # less than the expected size.
        self.socket.setblocking(0)

        timeout = self.params.timeout

        # If size isn't specified read up to 4096 bytes at a time.
        if size is None:
            recv_size = 4096
        else:
            recv_size = size

        data = []
        data_length = 0
        time_ = time.time()
        end = time_ + timeout
        while recv_size > 0:
            try:
                ready = select.select([self.socket], [], [], end - time_)
            except ValueError:
                return self._handle_abrupt_socket_close(size, data, time.time() - time_)
            if ready[0]:
                if (recv_data := self.socket.recv(recv_size)) == b"":
                    return self._handle_abrupt_socket_close(
                        size, data, time.time() - time_
                    )
                data.append(recv_data)
                data_length += len(recv_data)
            time_ = time.time()

            # If size isn't specified continue to read until timeout expires.
            if size:
                recv_size = size - data_length

            # Timeout is reduced also if some data has been received in order
            # to avoid infinite loops when there isn't an expected response
            # size and the slave sends noisy data continuously.
            if time_ > end:
                break

        return b"".join(data)

    def _handle_abrupt_socket_close(
        self, size, data, duration
    ):  # pylint: disable=missing-type-doc
        """Handle unexpected socket close by remote end.

        Intended to be invoked after determining that the remote end
        has unexpectedly closed the connection, to clean up and handle
        the situation appropriately.

        :param size: The number of bytes that was attempted to read
        :param data: The actual data returned
        :param duration: Duration from the read was first attempted
               until it was determined that the remote closed the
               socket
        :return: The more than zero bytes read from the remote end
        :raises ConnectionException: If the remote end didn't send any
                 data at all before closing the connection.
        """
        self.close()
        size_txt = size if size else "unbounded read"
        readsize = f"read of {size_txt} bytes"
        msg = (
            f"{self}: Connection unexpectedly closed "
            f"{duration} seconds into {readsize}"
        )
        if data:
            result = b"".join(data)
            Log.warning(" after returning {} bytes: {} ", len(result), result)
            return result
        msg += " without response from unit before it closed connection"
        raise ConnectionException(msg)

    def is_socket_open(self):
        """Check if socket is open."""
        return self.socket is not None

    def __str__(self):
        """Build a string representation of the connection.

        :returns: The string representation
        """
        return f"LSIS_TcpClient({self.params.host}:{self.params.port})"

    def __repr__(self):
        """Return string representation."""
        return (
            f"<{self.__class__.__name__} at {hex(id(self))} socket={self.socket}, "
            f"ipaddr={self.params.host}, port={self.params.port}, timeout={self.params.timeout}>"
        )
