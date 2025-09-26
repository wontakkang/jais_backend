from rest_framework import routers
from .views import SensorNodeConfigViewSet, ControlNodeConfigViewSet

router = routers.DefaultRouter()
router.register(r'sensor-node-configs', SensorNodeConfigViewSet)
router.register(r'control-node-configs', ControlNodeConfigViewSet)

urlpatterns = [
    *router.urls,
]
