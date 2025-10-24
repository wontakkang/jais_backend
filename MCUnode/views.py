# 상세 주석 추가: 파일 상단에 모듈 목적과 주요 동작 요약을 한글로 설명합니다.
# 이 파일은 DE-MCU 직렬 통신을 위한 DRF 뷰셋을 정의합니다.
# - MCUNodeConfigViewSet, IoTControllerConfigViewSet: 모델 CRUD용
# - DE_MCUSerialViewSet: POST 요청으로 DE-MCU 명령을 직렬 포트에 전송하고 응답을 반환하거나 없으면 시뮬레이션 응답을 반환
# - 에러 상황에서는 가능한 경우 클라이언트의 last_error를 우선 사용해 503을 반환합니다

import logging
import json
from rest_framework import viewsets, filters

from .models import MCUNodeConfig, IoTControllerConfig
from .serializers import MCUNodeConfigSerializer, IoTControllerConfigSerializer, DE_MCUSerialRequestSerializer
from utils.protocol.MCU.client.base import DE_MCU_SerialClient
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from pathlib import Path
from datetime import datetime
from . import logger, redis_instance
import binascii

def _iso_parse(s):
    """Try to parse ISO datetime strings robustly without external dependencies.
    Returns a datetime or None on failure.
    """
    if not s:
        return None
    try:
        # datetime.fromisoformat supports many ISO forms (Python 3.7+)
        return datetime.fromisoformat(s)
    except Exception:
        try:
            # strip trailing Z (UTC) and retry
            if isinstance(s, str) and s.endswith('Z'):
                return datetime.fromisoformat(s[:-1])
        except Exception:
            return None
    return None

class MCUNodeConfigViewSet(viewsets.ModelViewSet):
    # MCUNodeConfig 모델에 대한 표준 CRUD 뷰셋입니다.
    # queryset / serializer_class를 통해 기본 동작을 제공하므로 별도 커스터마이징이 필요 없을 때 사용합니다.
    queryset = MCUNodeConfig.objects.all()
    serializer_class = MCUNodeConfigSerializer


class IoTControllerConfigViewSet(viewsets.ModelViewSet):
    # IoTControllerConfig 모델에 대한 표준 CRUD 뷰셋입니다.
    queryset = IoTControllerConfig.objects.all()
    serializer_class = IoTControllerConfigSerializer


class DE_MCUSerialViewSet(viewsets.ViewSet):
    """DE-MCU 직렬 클라이언트용 ViewSet

    설명:
    - 클라이언트에서 POST로 요청 시, 전달된 포트와 명령을 사용해 DE-MCU PDU를 생성하고 직렬 포트로 전송합니다.
    - 실제 장치로부터 응답이 오면 이를 파싱하여 반환합니다. 응답이 없을 경우 내부적으로 시뮬레이션된 응답을 생성해 반환합니다.
    - 오류 처리: 직렬 통신 관련 오류(SerialException 또는 client.last_error 발생)는 503으로 반환하여 호출자가 재시도/대체 처리를 할 수 있도록 합니다.

    요청 예시 JSON:
    {
        "port": "COM6",
        "command": "NODE_SELECT_REQ",
        "serial_number": "4653500D004C003C"
        "req_data": ""
    }
    # SERIAL_SETUP : req_data(DDI) : {'Channel' : 1, 'Baudrate': 'BAUD_1200', 'SerialType': 'SDI', 'DataBits': 'SEVEN_BITS', 'Parity': 'EVEN', 'StopBits': 'ONE_BIT', 'FlowControl': 'NONE'}
    # SERIAL_WRITE : req_data(DDI) : {'Channel' : 1, 'Timeout': 1000, 'Data': '0I!'}
    # SERIAL_SETUP : req_data(RS485) : {'Channel' : 1, 'Baudrate': 9600, 'Type': 'RS485', 'Data_Bit': '8 Bit', 'Parity': 'NONE', 'Stop_Bit': '1 Bit', 'Flow_Control': 'NONE'}
    # SERIAL_WRITE : req_data(RS485) : {'Channel' : 1, 'Timeout': 1000, 'Data': '01 04 08 12 34 56 78 9A BC DE F0 CB FF'}
    """
    serializer_class = DE_MCUSerialRequestSerializer

    def list(self, request):
        # 브라우저에서 DRF의 Browsable API를 통해 POST 폼을 렌더링하기 위해 빈 200 응답을 반환.
        # 실제 목록 조회 기능은 필요하지 않으므로 간단히 200을 반환합니다.
        return Response(status=status.HTTP_200_OK)

    def create(self, request):
        # 최소한의 뷰 레벨 유효성 검증만 수행하고 상태 저장/직렬화는 context.manager로 위임합니다.
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        port = data.get('port')
        command = data.get('command')
        serial_bytes = data.get('serial_number')
        req_data = data.get('req_data')
        firmware_file = data.get('firmware_file', None)
        if firmware_file:
            try:
                req_data = firmware_file.read()
            except Exception as e:
                return Response({'detail': f'펌웨어 파일 읽기 실패: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        checksum_type = data.get('checksum_type', 'xor_simple')

        # 간단한 직렬 처리
        client = None
        try:
            # create client and perform transact. Keep kwargs structure as requested (serial_number passed through)
            client = DE_MCU_SerialClient(port=port)
            kwargs = {'command': command, 'checksum_type': checksum_type, 'serial_number': serial_bytes}
            if req_data not in (None, ''):
                kwargs['req_data'] = req_data
            # perform transact (may return object or dict). We normalize serial key separately below.
            res = client.transact(**kwargs)
            try:
                if res.get('processed_data') is not None:
                # Redis에 STATUS 데이터 저장 (필요시 활성화)
                    processed = res.get('processed_data')
                    # processed가 dict인지 확인하고 STATUS 키가 있는 경우에만 처리
                    if isinstance(processed, dict) and 'STATUS' in processed:
                        status_data = processed.get('STATUS')
                        if status_data:
                            try:
                                # serial_bytes가 bytes인 경우 16진수 문자열로 변환하여 Redis 키로 사용
                                if isinstance(serial_bytes, (bytes, bytearray)):
                                    key = binascii.hexlify(serial_bytes).decode()
                                else:
                                    key = str(serial_bytes)
                                redis_instance.hbulk_update(key, status_data)
                            except Exception as e:
                                logger.error(f"Redis STATUS 저장 실패: {e}")
                    if isinstance(processed, dict) and 'SETUP' in processed:
                        status_data = processed.get('SETUP')
                        if status_data:
                            try:
                                # serial_bytes가 bytes인 경우 16진수 문자열로 변환하여 Redis 키로 사용
                                if isinstance(serial_bytes, (bytes, bytearray)):
                                    key = binascii.hexlify(serial_bytes).decode()
                                else:
                                    key = str(serial_bytes)
                                redis_instance.hbulk_update(key, status_data)
                            except Exception as e:
                                logger.error(f"Redis SETUP 저장 실패: {e}")
            except Exception as e:
                logger.error(f"Redis 저장 실패: {e}")
            return Response(res, status=status.HTTP_200_OK)
        except Exception as e:
            # client.last_error 우선 사용
            err_msg = None
            try:
                if client is not None and getattr(client, 'last_error', None):
                    err_msg = client.last_error
            except Exception:
                err_msg = None

            exc_name = e.__class__.__name__ if e is not None else ''
            if err_msg or 'SerialException' in exc_name:
                return Response({'detail': err_msg or str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

