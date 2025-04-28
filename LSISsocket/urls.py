from rest_framework import routers
from .views import SocketClientConfigViewSet, SocketClientLogViewSet

router = routers.DefaultRouter()
router.register(r'client-configs', SocketClientConfigViewSet)
router.register(r'client-logs', SocketClientLogViewSet)
urlpatterns = router.urls