from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DeviceViewSet, ActivityViewSet, ControlHistoryViewSet, ControlRoleViewSet, IssueViewSet,
    ResolvedIssueViewSet, ScheduleViewSet, FacilityViewSet, ZoneViewSet, SensorDataViewSet,
    ControlSettingsViewSet, FacilityHistoryViewSet, CropViewSet, VarietyViewSet, VarietyImageViewSet, VarietyGuideViewSet,
    RecipeProfileViewSet, ControlItemViewSet, RecipeItemValueViewSet  # 추가된 ViewSet import
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
router.register(r'crops', CropViewSet)
router.register(r'varieties', VarietyViewSet)
router.register(r'variety-images', VarietyImageViewSet)
router.register(r'variety-guides', VarietyGuideViewSet)
router.register(r'recipe-profiles', RecipeProfileViewSet)  # 레시피 프로필
router.register(r'control-items', ControlItemViewSet)     # 제어 항목
router.register(r'recipe-item-values', RecipeItemValueViewSet)  # 레시피 항목 값

urlpatterns = [
    path('', include(router.urls)),
]