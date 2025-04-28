from rest_framework.views import exception_handler
import logging

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    # 기본 예외 처리기 호출
    response = exception_handler(exc, context)

    # HTTP 400 에러를 로깅
    if response is not None and response.status_code == 400:
        view = context.get('view', None)
        logger.error(f"400 Error in {view.__class__.__name__ if view else 'Unknown View'}: {exc}")
        logger.error(f"Details: {response.data}")

    return response