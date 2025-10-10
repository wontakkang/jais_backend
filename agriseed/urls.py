from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'devices', DeviceViewSet)
router.register(r'activities', ActivityViewSet)
router.register(r'control-histories', ControlHistoryViewSet)
router.register(r'control-roles', ControlRoleViewSet)
router.register(r'issues', IssueViewSet)
router.register(r'resolved-issues', ResolvedIssueViewSet)
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
router.register(r'recipe-steps', RecipeStepViewSet)  # 레시피 단계 값
router.register(r'control-items', ControlItemViewSet)     # 제어 항목
router.register(r'recipe-item-values', RecipeItemValueViewSet)  # 레시피 항목 값
router.register(r'sensor-items', SensorItemViewSet)
router.register(r'measurement-items', MeasurementItemViewSet)
router.register(r'recipe-comments', RecipeCommentViewSet, basename='recipe-comment')  # 레시피 코멘트
router.register(r'comment-votes', RecipeCommentVoteViewSet, basename='comment-vote')  # 코멘트 도움됨/도움안됨
router.register(r'recipe-performances', RecipePerformanceViewSet, basename='recipe-performance')  # 레시피 성과
router.register(r'recipe-ratings', RecipeRatingViewSet, basename='recipe-rating')  # 레시피 별점
router.register(r'recipe-by-zone', RecipeByZoneViewSet, basename='recipe-by-zone')

# Tree 관련 엔드포인트 등록
router.register(r'trees', TreeViewSet)
router.register(r'tree-tags', TreeTagsViewSet)
router.register(r'tree-images', TreeImageViewSet)
router.register(r'specimens', SpecimenDataViewSet)
router.register(r'specimen-attachments', SpecimenAttachmentViewSet)

# VarietyDataThreshold 및 QualityEvent 엔드포인트 등록
router.register(r'variety-data-thresholds', VarietyDataThresholdViewSet)
router.register(r'quality-events', QualityEventViewSet)

# Calendar 및 Todo 엔드포인트 등록
router.register(r'calendar-events', CalendarEventViewSet)
router.register(r'calendar-schedules', CalendarScheduleViewSet)
router.register(r'todos', TodoItemViewSet)

router.register(r'control-values', ControlValueViewSet)
router.register(r'control-value-histories', ControlValueHistoryViewSet)
router.register(r'calc-variables', CalcVariableViewSet)
router.register(r'calc-groups', CalcGroupViewSet)
router.register(r'control-groups', ControlGroupViewSet)
router.register(r'control-variables', ControlVariableViewSet)


router.register(r'location-groups', LocationGroupViewSet)
router.register(r'location-codes', LocationCodeViewSet)
router.register(r'modules', ModuleViewSet)

router.register(r'device-instances', DeviceInstanceViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('agriseed/qr/<str:identifier>/', qr_image, name='agriseed-qr'),
    # 측정값 평가용 단일 엔드포인트
    path('evaluate-measurement/', EvaluateMeasurementView.as_view(), name='evaluate-measurement'),
]

# Expose corecode URLs under /agriseed/core/ to reuse core endpoints when corecode app is present.
try:
    # include already imported at top
    urlpatterns += [
        path('core/', include('corecode.urls')),
    ]
except Exception:
    # corecode may not be installed/available in some environments (tests/tools) — ignore silently
    pass
