from rest_framework import viewsets
from .models import *
from .serializers import *
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

# -------------------
# 이 ViewSet은 장치, 활동, 제어 이력, 역할, 이슈, 스케줄, 시설, 구역, 센서 데이터 등 농업 자동화 시스템의 주요 엔터티에 대한 CRUD API를 제공합니다.
# 주요 기능:
#   - 각 모델별 생성/조회/수정/삭제
#   - RESTful 엔드포인트 제공 (예: /devices/, /activities/ 등)
#   - Django REST framework의 ModelViewSet 기반 자동 API
#
# 사용 예시:
#   GET /devices/ (장치 목록 조회)
#   POST /activities/ (활동 생성)
#   PATCH /zones/1/ (구역 정보 수정)
#   DELETE /crops/2/ (작물 삭제)
# -------------------

# DeviceViewSet: 장치(Device) 모델의 CRUD API를 제공합니다.
class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer

# ActivityViewSet: 활동(Activity) 모델의 CRUD API를 제공합니다.
class ActivityViewSet(viewsets.ModelViewSet):
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer

# ControlHistoryViewSet: 제어 이력(ControlHistory) 모델의 CRUD API를 제공합니다.
class ControlHistoryViewSet(viewsets.ModelViewSet):
    queryset = ControlHistory.objects.all()
    serializer_class = ControlHistorySerializer

# ControlRoleViewSet: 제어 역할(ControlRole) 모델의 CRUD API를 제공합니다.
class ControlRoleViewSet(viewsets.ModelViewSet):
    queryset = ControlRole.objects.all()
    serializer_class = ControlRoleSerializer

# IssueViewSet: 이슈(Issue) 모델의 CRUD API를 제공합니다.
class IssueViewSet(viewsets.ModelViewSet):
    queryset = Issue.objects.all()
    serializer_class = IssueSerializer

# ResolvedIssueViewSet: 해결된 이슈(ResolvedIssue) 모델의 CRUD API를 제공합니다.
class ResolvedIssueViewSet(viewsets.ModelViewSet):
    queryset = ResolvedIssue.objects.all()
    serializer_class = ResolvedIssueSerializer

# ScheduleViewSet: 스케줄(Schedule) 모델의 CRUD API를 제공합니다.
class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer

# FacilityViewSet: 시설(Facility) 모델의 CRUD API를 제공합니다.
class FacilityViewSet(viewsets.ModelViewSet):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer

# ZoneViewSet: 구역(Zone) 모델의 CRUD API를 제공합니다.
class ZoneViewSet(viewsets.ModelViewSet):
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer

# SensorDataViewSet: 센서 데이터(SensorData) 모델의 CRUD API를 제공합니다.
class SensorDataViewSet(viewsets.ModelViewSet):
    queryset = SensorData.objects.all()
    serializer_class = SensorDataSerializer

# ControlSettingsViewSet: 제어 설정(ControlSettings) 모델의 CRUD API를 제공합니다.
class ControlSettingsViewSet(viewsets.ModelViewSet):
    queryset = ControlSettings.objects.all()
    serializer_class = ControlSettingsSerializer

# FacilityHistoryViewSet: 시설 이력(FacilityHistory) 모델의 CRUD API를 제공합니다.
class FacilityHistoryViewSet(viewsets.ModelViewSet):
    queryset = FacilityHistory.objects.all()
    serializer_class = FacilityHistorySerializer

# CropViewSet: 작물(Crop) 모델의 CRUD API를 제공합니다.
class CropViewSet(viewsets.ModelViewSet):
    queryset = Crop.objects.all()
    serializer_class = CropSerializer

# VarietyViewSet: 품종(Variety) 모델의 CRUD API를 제공합니다.
class VarietyViewSet(viewsets.ModelViewSet):
    queryset = Variety.objects.all()
    serializer_class = VarietySerializer

# VarietyImageViewSet: 품종 이미지(VarietyImage) 모델의 CRUD API를 제공합니다.
class VarietyImageViewSet(viewsets.ModelViewSet):
    queryset = VarietyImage.objects.all()
    serializer_class = VarietyImageSerializer

# VarietyGuideViewSet: 품종 가이드(VarietyGuide) 모델의 CRUD API를 제공합니다.
class VarietyGuideViewSet(viewsets.ModelViewSet):
    queryset = VarietyGuide.objects.all()
    serializer_class = VarietyGuideSerializer

# 신규 ViewSets 추가
class RecipeProfileViewSet(viewsets.ModelViewSet):
    # 기본적으로 삭제되지 않은 레시피만 조회
    queryset = RecipeProfile.objects.filter(is_deleted=False)
    serializer_class = RecipeProfileSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['variety__id', 'recipe_name', 'is_active', 'is_deleted']
    ordering_fields = ['order', 'id']

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

class ControlItemViewSet(viewsets.ModelViewSet):
    queryset = ControlItem.objects.all()
    serializer_class = ControlItemSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['item_name']
    ordering_fields = ['id', 'item_name']

class RecipeItemValueViewSet(viewsets.ModelViewSet):
    queryset = RecipeItemValue.objects.all()
    serializer_class = RecipeItemValueSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['recipe__id', 'control_item__id']
    ordering_fields = ['id']

class RecipeStepViewSet(viewsets.ModelViewSet):
    """RecipeStep 모델의 CRUD API"""
    queryset = RecipeStep.objects.all()
    serializer_class = RecipeStepSerializer
    # 필터, 검색, 정렬 지원
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['recipe_profile', 'name', 'order', 'duration_days']
    search_fields = ['name', 'description']
    ordering_fields = ['order', 'id']
