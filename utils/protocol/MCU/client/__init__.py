from .base import DE_MCU_SerialClient

__all__ = [
    "DE_MCU_SerialClient",
]

# 사용 예시:
# from utils.protocol.MCU.client import DE_MCU_SerialClient
#
# # 시리얼 클라이언트 생성 (포트, 보드레이트 등은 환경에 맞게 설정)
# client = DE_MCU_SerialClient(port='COM3', baudrate=9600, timeout=1)
# client.connect()
# try:
#     # 전송할 페이로드(바이트열) 예시
#     payload = b'\x01\x02\x03'
#     # 요청 전송 및 응답 수신 (메서드 이름은 DE_MCU_SerialClient 구현에 따라 달라질 수 있음)
#     response = client.send_and_receive(payload)
#     # 응답 처리
#     # ...응답 검사/파싱 코드...
# finally:
#     client.close()
