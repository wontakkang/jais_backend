from rest_framework import routers
from .views import *

router = routers.DefaultRouter()
router.register(r'client-configs', SocketClientConfigViewSet)
router.register(r'sensor-node-configs', SensorNodeConfigViewSet)
router.register(r'control-node-configs', ControlNodeConfigViewSet)
router.register(r'client-logs', SocketClientLogViewSet)
router.register(r'client-commands', SocketClientCommandViewSet)
router.register(r'adapters', AdapterViewSet)
urlpatterns = router.urls