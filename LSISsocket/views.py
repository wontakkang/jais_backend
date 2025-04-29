from django.http import JsonResponse
from .service import lsis_init_and_reset, lsis_stop, lsis_run

# 초기 통신 및 리셋
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets
from .models import *
from .serializers import *

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

@csrf_exempt
@require_POST
def lsis_init_reset_view(request):
    host = request.GET.get("host")
    port = request.GET.get("port")
    print(f"host: {host}, port: {port}")
    if not host or not port:
        return JsonResponse({"detail": "host, port 파라미터가 필요합니다."}, status=400)
    try:
        port = int(port)
        result = lsis_init_and_reset(host, port)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"detail": str(e)}, status=500)

@csrf_exempt
@require_POST
def lsis_stop_view(request):
    host = request.GET.get("host")
    port = request.GET.get("port")
    if not host or not port:
        return JsonResponse({"detail": "host, port 파라미터가 필요합니다."}, status=400)
    try:
        port = int(port)
        result = lsis_stop(host, port)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"detail": str(e)}, status=500)

@csrf_exempt
@require_POST
def lsis_run_view(request):
    host = request.GET.get("host")
    port = request.GET.get("port")
    if not host or not port:
        return JsonResponse({"detail": "host, port 파라미터가 필요합니다."}, status=400)
    try:
        port = int(port)
        result = lsis_run(host, port)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"detail": str(e)}, status=500)
