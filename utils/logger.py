import logging
import logging.handlers
import os, sys

def setup_logger(name="sql_logger", log_file="log/sql_queries.log", level=logging.DEBUG, backup_days=7):
    """
    설정된 로거를 반환합니다.
    
    :param name: 로거 이름
    :param log_file: 로그를 저장할 파일 경로
    :param level: 로깅 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    :param backup_days: 보관할 최대 일수 (이 초과된 로그 파일은 자동 삭제됨)
        
    # 로거 설정 및 사용 예제
    logger = setup_logger(log_file="sql_queries.log", backup_days=7)
    logger.info("이 로그는 특정 기간 이후 자동으로 삭제됩니다.")
    """
    # 로거 생성
    logger = logging.getLogger(name)
    # 문자열로 "INFO", "DEBUG" 등 전달 가능하도록 처리
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.DEBUG)
    logger.setLevel(level)

    # 이미 핸들러가 있으면 중복 추가를 방지하고 레벨만 갱신하여 반환
    if logger.handlers:
        for h in logger.handlers:
            h.setLevel(level)
        return logger

        # 파일 핸들러 (기간별 롤링)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file, when="midnight", interval=1, backupCount=backup_days, encoding="utf-8"
    )
    
    # 문자열로 "INFO", "DEBUG" 등 전달 가능하도록 처리
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.DEBUG)
    file_handler.setLevel(level)

    # 콘솔 핸들러 생성
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    
    # 문자열로 "INFO", "DEBUG" 등 전달 가능하도록 처리
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.DEBUG)
    console_handler.setLevel(level)
    
    formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 핸들러 추가
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# 📌 2. 예외 발생 시 자동으로 로깅하는 데코레이터
def log_exceptions(logger):
    """
    예외가 발생하면 자동으로 로거에 기록하는 데코레이터.
    # 📌 3. 로거 생성
    logger = setup_logger()

    # 📌 4. 데코레이터 적용하여 자동 예외 로깅
    @log_exceptions(logger)
    def faulty_function():
        return 1 / 0  # ZeroDivisionError 발생

    # 📌 5. 실행 (예외 발생 시 자동으로 로그 기록됨)
    try:
        faulty_function()
    except Exception as e:
        print("⚠️ 오류 발생, 로그를 확인하세요.")
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                filename = exc_traceback.tb_frame.f_code.co_filename
                line_no = exc_traceback.tb_lineno
                error_message = f"🚨 [ERROR] {func.__name__}()에서 예외 발생 🚨\n" \
                                f"📌 파일: {filename}, 라인: {line_no}\n" \
                                f"📍 오류 메시지: {exc_value}\n"
                logger.error(error_message, exc_info=True)
                raise  # 예외를 다시 발생시켜 호출자가 처리할 수 있도록 함
        return wrapper
    return decorator
