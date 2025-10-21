from django.urls import path, include
from rest_framework import routers
from .views import MCUNodeConfigViewSet, IoTControllerConfigViewSet, DE_MCUSerialViewSet, StateViewSet

router = routers.DefaultRouter()
router.register(r'nodes', MCUNodeConfigViewSet, basename='mcu-node')
router.register(r'controllers', IoTControllerConfigViewSet, basename='iot-controller')
router.register(r'de-mcu', DE_MCUSerialViewSet, basename='de-mcu')
router.register(r'state', StateViewSet, basename='state')

urlpatterns = [
    path('', include(router.urls)),
]
