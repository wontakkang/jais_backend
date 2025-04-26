from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DeviceViewSet, ActivityViewSet, ControlHistoryViewSet, ControlRoleViewSet, IssueViewSet,
    ResolvedIssueViewSet, ScheduleViewSet, FacilityViewSet, ZoneViewSet, SensorDataViewSet,
    ControlSettingsViewSet, FacilityHistoryViewSet
)

router = DefaultRouter()
router.register(r'devices', DeviceViewSet)
router.register(r'activities', ActivityViewSet)
router.register(r'control-histories', ControlHistoryViewSet)
router.register(r'control-roles', ControlRoleViewSet)
router.register(r'issues', IssueViewSet)
router.register(r'resolved-issues', ResolvedIssueViewSet)
router.register(r'schedules', ScheduleViewSet)
router.register(r'facilities', FacilityViewSet)
router.register(r'zones', ZoneViewSet)
router.register(r'sensor-data', SensorDataViewSet)
router.register(r'control-settings', ControlSettingsViewSet)
router.register(r'facility-histories', FacilityHistoryViewSet)

urlpatterns = [
    path('', include(router.urls)),
]