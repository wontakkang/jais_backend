from rest_framework import routers
from .views import *
from django.urls import include, path
from .views import LSISInitResetView, LSISStopView, LSISRunView

router = routers.DefaultRouter()
router.register(r'client-configs', SocketClientConfigViewSet)
router.register(r'client-status', SocketClientStatusViewSet)
router.register(r'client-logs', SocketClientLogViewSet)
router.register(r'sensor-node-configs', SensorNodeConfigViewSet)
router.register(r'control-node-configs', ControlNodeConfigViewSet)
router.register(r'client-commands', SocketClientCommandViewSet)
router.register(r'adapters', AdapterViewSet)
urlpatterns = [
    *router.urls,
    # LSIS 명령 API
    path('cpu/init-reset/', LSISInitResetView.as_view(), name='lsis-init-reset'),
    path('cpu/stop/', LSISStopView.as_view(), name='lsis-cpu-stop'),
    path('cpu/run/', LSISRunView.as_view(), name='lsis-cpu-run'),
]