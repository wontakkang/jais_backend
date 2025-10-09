import time
from rest_framework import viewsets, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend
from utils.protocol.LSIS.client.tcp import LSIS_TcpClient
from .models import *
from .serializers import *
import logging, asyncio
logger = logging.getLogger(__name__)
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

# -------------------
# 이 ViewSet들은 소켓 클라이언트, 센서/제어 노드 등 설비 통신 및 상태 관리의 CRUD API를 제공합니다.
# 주요 기능:
#   - 각 모델별 생성/조회/수정/삭제
#   - 소켓 클라이언트 상태 필터링/정렬 지원
#   - 설비 통신 명령(초기화, 정지, 실행) API 별도 제공 (APIView 기반)
#   - Django REST framework의 ModelViewSet 기반 자동 API
#
# 사용 예시:
#   GET /socket-client-configs/ (설정 목록 조회)
#   POST /socket-client-commands/ (명령 생성)
#   POST /lsisinitreset/ {"host": "1.2.3.4", "port": 1234} (초기화 명령)
#   POST /lsisstop/ {"host": "1.2.3.4", "port": 1234} (정지 명령)
#   POST /lsisrun/ {"host": "1.2.3.4", "port": 1234} (실행 명령)
# -------------------


class VariableViewSet(viewsets.ModelViewSet):
    """
    변수(Variable) 모델의 CRUD API를 제공합니다.
    각 Variable 인스턴스는 group 필드를 통해 MemoryGroup과 연결되어 있습니다.
    """
    queryset = Variable.objects.all()
    serializer_class = VariableSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['group__id']
    ordering_fields = ['id']
    
class MemoryGroupViewSet(viewsets.ModelViewSet):
    """
    메모리 그룹(MemoryGroup) 모델의 CRUD API를 제공합니다.
    각 MemoryGroup 인스턴스는 여러 Variable과 연결되어 있습니다.
    """
    queryset = MemoryGroup.objects.all()
    serializer_class = MemoryGroupSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['id', 'name', 'Device', 'Device__name']
    ordering_fields = ['id', 'name']
    
    
# SocketClientConfigViewSet: 소켓 클라이언트 설정 모델의 CRUD API를 제공합니다.
class SocketClientConfigViewSet(viewsets.ModelViewSet):
    queryset = SocketClientConfig.objects.all()
    serializer_class = SocketClientConfigSerializer

# SocketClientLogViewSet: 소켓 클라이언트 로그 모델의 CRUD API를 제공합니다.
class SocketClientLogViewSet(viewsets.ModelViewSet):
    queryset = SocketClientLog.objects.all()
    serializer_class = SocketClientLogSerializer

# SocketClientCommandViewSet: 소켓 클라이언트 명령 모델의 CRUD API를 제공합니다.
class SocketClientCommandViewSet(viewsets.ModelViewSet):
    queryset = SocketClientCommand.objects.all()
    serializer_class = SocketClientCommandSerializer

# SocketClientStatusViewSet: 소켓 클라이언트 상태 모델의 CRUD API를 제공합니다.
class SocketClientStatusViewSet(viewsets.ModelViewSet):
    queryset = SocketClientStatus.objects.all()
    serializer_class = SocketClientStatusSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['config__id']
    ordering_fields = ['id', 'updated_at']


def lsis_init_and_reset(host, port, user=None):
    from LSISsocket.models import SocketClientCommand, SocketClientConfig  # django.setup() 이후 import
    try:
        client = LSIS_TcpClient(host, port)
        client.connect()
        client.send_first_communication()
        client.send_stop()
        response = client.send_reset()
        client.close()
        # 명령 이력 저장
        SocketClientCommand.objects.create(
            config=SocketClientConfig.objects.filter(host=host, port=port).first(),
            user=user or '',
            command='init_reset',
            value='success',
            response='',
            payload={'host': host, 'port': port},
            message='초기 통신 및 리셋 명령 전송',
        )
        return {"detail": "초기 통신 및 리셋 명령 전송 완료"}
    except Exception as e:
        # 명령 이력 저장
        SocketClientCommand.objects.create(
            config=SocketClientConfig.objects.filter(host=host).first(),
            user=user or '',
            command='init_reset',
            value='failure',
            response=str(e),
            payload={'host': host, 'port': port},
            message='init_reset 명령 전송 실패',
        )
        return {"detail": "init_reset 명령 전송 실패", "error": str(e)}

def lsis_stop(host, port, user=None):
    from LSISsocket.models import SocketClientCommand, SocketClientConfig  # django.setup() 이후 import
    try:
        client = LSIS_TcpClient(host, port)
        client.connect()
        client.send_first_communication()
        response = client.send_stop()
        client.close()
        # 명령 이력 저장
        SocketClientCommand.objects.create(
            config=SocketClientConfig.objects.filter(host=host).first(),
            user=user or '',
            command='stop',
            value='success',
            response='',
            payload={'host': host, 'port': port},
            message='STOP 명령 전송',
        )
        return {"detail": "STOP 명령 전송 완료"}
    except Exception as e:
        # 명령 이력 저장
        SocketClientCommand.objects.create(
            config=SocketClientConfig.objects.filter(host=host).first(),
            user=user or '',
            command='stop',
            value='failure',
            response=str(e),
            payload={'host': host, 'port': port},
            message='STOP 명령 전송 실패',
        )
        return {"detail": "STOP 명령 전송 실패", "error": str(e)}


def lsis_run(host, port, user=None):
    from LSISsocket.models import SocketClientCommand, SocketClientConfig  # django.setup() 이후 import
    try:
        client = LSIS_TcpClient(host, port)
        client.connect()
        client.send_first_communication()
        response = client.send_start()
        client.close()
        # 명령 이력 저장
        SocketClientCommand.objects.create(
            config=SocketClientConfig.objects.filter(host=host).first(),
            user=user or '',
            command='run',
            value='success',
            response='',
            payload={'host': host, 'port': port},
            message='RUN 명령 전송 완료',
        )
        return {"detail": "RUN 명령 전송 완료"}
    except Exception as e:
        # 명령 이력 저장
        SocketClientCommand.objects.create(
            config=SocketClientConfig.objects.filter(host=host).first(),
            user=user or '',
            command='run',
            value='failure',
            response=str(e),
            payload={'host': host, 'port': port},
            message='RUN 명령 전송 실패',
        )
        return {"detail": "RUN 명령 전송 실패", "error": str(e)}

@method_decorator(csrf_exempt, name='dispatch')
class LSISInitResetView(APIView):
    def post(self, request, *args, **kwargs):
        data = request.data
        host = data.get("host")
        port = data.get("port")
        logger.info(f"lsis_init_reset_view called: host={host}, port={port}")
        if not host or not port:
            logger.warning("host, port 파라미터가 필요합니다.")
            return JsonResponse({"detail": "host, port 파라미터가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            port = int(port)
            result = lsis_init_and_reset(host, port)
            logger.info(f"lsis_init_and_reset result: {result}")
            return JsonResponse(result)
        except Exception as e:
            logger.exception(f"lsis_init_reset_view error: {e}")
            return JsonResponse({"detail": str(e)}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class LSISStopView(APIView):
    def post(self, request, *args, **kwargs):
        data = request.data
        host = data.get("host")
        port = data.get("port")
        logger.info(f"lsis_stop_view called: host={host}, port={port}")
        if not host or not port:
            logger.warning("host, port 파라미터가 필요합니다.")
            return JsonResponse({"detail": "host, port 파라미터가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            port = int(port)
            result = lsis_stop(host, port)
            logger.info(f"lsis_stop result: {result}")
            return JsonResponse(result)
        except Exception as e:
            logger.exception(f"lsis_stop_view error: {e}")
            return JsonResponse({"detail": str(e)}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class LSISRunView(APIView):
    def post(self, request, *args, **kwargs):
        data = request.data
        host = data.get("host")
        port = data.get("port")
        logger.info(f"lsis_run_view called: host={host}, port={port}")
        if not host or not port:
            logger.warning("host, port 파라미터가 필요합니다.")
            return JsonResponse({"detail": "host, port 파라미터가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            port = int(port)
            result = lsis_run(host, port)
            logger.info(f"lsis_run result: {result}")
            return JsonResponse(result)
        except Exception as e:
            logger.exception(f"lsis_run_view error: {e}")
            return JsonResponse({"detail": str(e)}, status=500)
