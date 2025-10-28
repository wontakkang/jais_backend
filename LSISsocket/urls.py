from rest_framework import routers
from .views import *
from django.urls import path
from .views import LSISInitResetView, LSISStopView, LSISRunView

router = routers.DefaultRouter()
router.register(r'client-configs', SocketClientConfigViewSet)
router.register(r'client-status', SocketClientStatusViewSet)
router.register(r'client-logs', SocketClientLogViewSet)
router.register(r'client-commands', SocketClientCommandViewSet)
# adapters 엔드포인트는 corecode로 이전됨
# router.register(r'adapters', AdapterViewSet)
# 메모리 그룹 및 변수 API는 LSISsocket에서 제공되어야 하므로 등록을 복구합니다.
router.register(r'memory-groups', MemoryGroupViewSet, basename='memorygroup')
router.register(r'memory-variables', VariableViewSet, basename='variable')
router.register(r'control-values', ControlValueViewSet)
router.register(r'control-value-histories', ControlValueHistoryViewSet)
router.register(r'calc-variables', CalcVariableViewSet)
router.register(r'calc-groups', CalcGroupViewSet)
router.register(r'control-groups', ControlGroupViewSet)
router.register(r'control-variables', ControlVariableViewSet)
router.register(r'alart-variables', AlartVariableViewSet)
router.register(r'alart-groups', AlartGroupViewSet)
# New: setup groups only (variables selection moved into group M2M)
router.register(r'setup-groups', SetupGroupViewSet)

urlpatterns = [
    *router.urls,
    # LSIS 명령 API
    path('cpu/init-reset/', LSISInitResetView.as_view(), name='lsis-init-reset'),
    path('cpu/stop/', LSISStopView.as_view(), name='lsis-cpu-stop'),
    path('cpu/run/', LSISRunView.as_view(), name='lsis-cpu-run'),
]