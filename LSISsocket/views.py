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

class SocketClientConfigViewSet(viewsets.ModelViewSet):
    queryset = SocketClientConfig.objects.all()
    serializer_class = SocketClientConfigSerializer

class SocketClientLogViewSet(viewsets.ModelViewSet):
    queryset = SocketClientLog.objects.all()
    serializer_class = SocketClientLogSerializer

class SocketClientCommandViewSet(viewsets.ModelViewSet):
    queryset = SocketClientCommand.objects.all()
    serializer_class = SocketClientCommandSerializer

class SensorNodeConfigViewSet(viewsets.ModelViewSet):
    queryset = SensorNodeConfig.objects.all()
    serializer_class = SensorNodeConfigSerializer

class ControlNodeConfigViewSet(viewsets.ModelViewSet):
    queryset = ControlNodeConfig.objects.all()
    serializer_class = ControlNodeConfigSerializer

class AdapterViewSet(viewsets.ModelViewSet):
    queryset = Adapter.objects.all()
    serializer_class = AdapterSerializer

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
            value='failure",',
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
            value='failure",',
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
            value='failure",',
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
