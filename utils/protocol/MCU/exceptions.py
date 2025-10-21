import logging
import traceback

from .config import DE_MCU_constants, get_mcu_config
logger = get_mcu_config().get_logger()


class DE_MCU_Exception(Exception):
    """DE-MCU 관련 예외 클래스.

    생성 시 메시지와 선택적 원래 예외(exc)을 전달하면 즉시 로깅합니다.
    로그 레벨은 level 인수로 지정할 수 있습니다.
    """

    def __init__(self, message: str, exc: Exception = None, level: str = "error"):
        super().__init__(message)
        self.message = str(message)
        self.exc = exc
        self.level = (level or "error").lower()
        # 생성과 동시에 로그를 남김
        try:
            self.log()
        except Exception:
            # 로깅 실패 시 예외가 전파되는 것을 방지
            logger.exception("Failed to log DE_MCU_Exception")

    def log(self):
        """예외 정보를 로거에 기록합니다."""
        msg = f"DE_MCU_Exception: {self.message}"
        if self.exc is not None:
            tb = "".join(
                traceback.format_exception(
                    type(self.exc), self.exc, self.exc.__traceback__
                )
            )
            msg = f"{msg}\nCaused by:\n{tb}"

        if self.level == "debug":
            logger.debug(msg)
        elif self.level in ("warn", "warning"):
            logger.warning(msg)
        elif self.level == "info":
            logger.info(msg)
        elif self.level == "critical":
            logger.critical(msg)
        else:
            logger.error(msg)

    @staticmethod
    def log_exception(exc: Exception, context: str = None, level: str = "error"):
        """외부에서 예외를 받아 로깅만 수행할 때 사용합니다."""
        context_msg = f"Context: {context} - " if context else ""
        try:
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        except Exception:
            tb = repr(exc)
        msg = f"{context_msg}{tb}"
        lvl = (level or "error").lower()
        if lvl == "debug":
            logger.debug(msg)
        elif lvl in ("warn", "warning"):
            logger.warning(msg)
        elif lvl == "info":
            logger.info(msg)
        elif lvl == "critical":
            logger.critical(msg)
        else:
            logger.error(msg)

    @staticmethod
    def raise_with_log(message: str, exc: Exception = None, level: str = "error"):
        """로그를 남기고 DE_MCU_Exception을 발생시킵니다."""
        # 로그 후 예외 발생
        DE_MCU_Exception.log_exception(
            exc if exc is not None else Exception(message), context=message, level=level
        )
        raise DE_MCU_Exception(message, exc=exc, level=level)


class ConnectionException(DE_MCU_Exception):
    """연결(소켓/시리얼/네트워크) 관련 예외.

    추가 컨텍스트(host, port, endpoint, retryable)를 메시지에 포함하여 자동 로깅합니다.
    """

    def __init__(
        self,
        message: str,
        exc: Exception | None = None,
        level: str = "error",
        *,
        host: str | None = None,
        port: int | None = None,
        endpoint: str | None = None,
        retryable: bool | None = None,
    ):
        ctx = []
        if endpoint:
            ctx.append(f"endpoint={endpoint}")
        if host is not None:
            ctx.append(f"host={host}")
        if port is not None:
            ctx.append(f"port={port}")
        if retryable is not None:
            ctx.append(f"retryable={retryable}")
        full_message = f"{message} ({', '.join(ctx)})" if ctx else message
        super().__init__(full_message, exc=exc, level=level)
