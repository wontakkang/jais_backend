from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import TwoMinuteDataViewSet, TenMinuteDataViewSet, HourlyDataViewSet, DailyDataViewSet, RedisKeyViewSet

router = DefaultRouter()
router.register(r'2min', TwoMinuteDataViewSet, basename='two-minute')
router.register(r'10min', TenMinuteDataViewSet, basename='ten-minute')
router.register(r'1hour', HourlyDataViewSet, basename='hourly')
router.register(r'daily', DailyDataViewSet, basename='daily')
router.register(r'redis', RedisKeyViewSet, basename='redis')

urlpatterns = [
    path('', include(router.urls)),
]