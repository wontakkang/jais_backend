from rest_framework import viewsets
from .models import *
from .serializers import *
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from django.db.models import Count, Avg, Q, Prefetch
from django.db import IntegrityError
from rest_framework.pagination import PageNumberPagination
from django_filters import rest_framework as df_filters
import json
from rest_framework.views import APIView
from utils.custom_permission import CreatedByOrStaffPermission
from rest_framework.metadata import SimpleMetadata
from rest_framework.relations import PrimaryKeyRelatedField
from rest_framework import serializers as drf_serializers

class StyleMetadata(SimpleMetadata):
    def get_field_info(self, field):
        info = super().get_field_info(field)
        # Preserve default if present and not DRF empty sentinel
        default_val = getattr(field, 'default', drf_serializers.empty)
        if default_val is not drf_serializers.empty:
            info['default'] = default_val
        # Ensure there is a style dict and inject defaults to avoid missing keys
        style = info.get('style') if isinstance(info.get('style'), dict) else {}
        # copy any field-level style attached to the serializer.Field instance
        if hasattr(field, 'style') and isinstance(getattr(field, 'style'), dict):
            # merge but keep existing keys in field.style
            merged = {**style, **getattr(field, 'style')}
            style = merged
        # default style entries
        style.setdefault('example', None)
        style.setdefault('type', None)
        style.setdefault('format', None)
        info['style'] = style
        if hasattr(field, 'style'):
            info['style_source'] = 'field'
        # Mark related fields
        if isinstance(field, PrimaryKeyRelatedField):
            info['type'] = 'related'
            queryset = getattr(field, 'queryset', None)
            if queryset is not None:
                model = queryset.model
                info['target'] = model.__name__
                # determine display attribute
                if hasattr(model, 'name'):
                    info['field'] = 'name'
                elif hasattr(model, 'username'):
                    info['field'] = 'username'
                else:
                    info['field'] = None
        # Sanitize any non-JSON-serializable objects to strings (types, callables, etc.)
        def sanitize(obj):
            # types
            if isinstance(obj, type):
                return obj.__name__
            # callables (functions, lambdas, callables returning default)
            if callable(obj):
                try:
                    return getattr(obj, '__name__', str(obj))
                except Exception:
                    return str(obj)
            # dict / list recursion
            if isinstance(obj, dict):
                return {k: sanitize(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [sanitize(v) for v in obj]
            return obj

        return sanitize(info)

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

# Default pagination and filtering/search/ordering
class DefaultPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class BaseViewSet(viewsets.ModelViewSet):
    pagination_class = DefaultPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = []  # override in subclasses if needed
    ordering_fields = ['id']  # override in subclasses

# DeviceViewSet: 장치(Device) 모델의 CRUD API를 제공합니다.
class DeviceViewSet(BaseViewSet):
    # Device 모델에 맞게 queryset 및 필터/검색/정렬 필드 조정
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    filterset_fields = ['device_id', 'type', 'is_deleted']
    search_fields = ['name', 'device_id', 'location']
    ordering_fields = ['id', 'installed_at']

# ActivityViewSet: 활동(Activity) 모델의 CRUD API를 제공합니다.
class ActivityViewSet(viewsets.ModelViewSet):
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer

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
class CalendarScheduleViewSet(viewsets.ModelViewSet):
    # CalendarSchedule now references crop and variety instead of zone-related fields
    queryset = CalendarSchedule.objects.select_related('facility', 'zone', 'crop', 'variety', 'recipe_profile', 'created_by').all()
    serializer_class = CalendarScheduleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['facility', 'zone', 'crop', 'variety', 'recipe_profile', 'enabled', 'completed', 'is_deleted']
    ordering_fields = ['created_at', 'sowing_date', 'expected_harvest_date', 'id']

    def perform_create(self, serializer):
        # set created_by when creating via API if user is authenticated
        user = self.request.user if getattr(self.request, 'user', None) and self.request.user.is_authenticated else None
        try:
            serializer.save(created_by=user)
        except TypeError:
            serializer.save()

    def perform_update(self, serializer):
        # preserve created_by but allow updating other fields
        user = self.request.user if getattr(self.request, 'user', None) and self.request.user.is_authenticated else None
        try:
            serializer.save()
        except TypeError:
            serializer.save()

# FacilityViewSet: 시설(Facility) 모델의 CRUD API를 제공합니다.
class FacilityViewSet(viewsets.ModelViewSet):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer

# ZoneViewSet: 구역(Zone) 모델의 CRUD API를 제공합니다.
class ZoneViewSet(BaseViewSet):
    """구역(Zone) 모델의 CRUD API - facility 연동 및 기본 검증 포함"""
    # Zone은 단일 recipe_profile(FK)을 가짐 -> select_related로 조인하여 N+1 문제 완화
    queryset = Zone.objects.select_related('facility', 'updated_by').all()
    serializer_class = ZoneSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # recipe_profile(FK)로 필터 가능 (예: ?recipe_profile=1)
    filterset_fields = ['facility', 'status', 'health_status', 'environment_status', 'is_deleted']
    search_fields = ['name', 'style']
    ordering_fields = ['id', 'area']

    def perform_create(self, serializer):
        facility = serializer.validated_data.get('facility')
        name = serializer.validated_data.get('name')
        # 같은 시설내 중복 이름 방지
        if facility and name and Zone.objects.filter(facility=facility, name=name).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'name': '같은 시설에 동일한 구역 이름이 이미 존재합니다.'})
        # 전달 가능한 경우 created_by/updated_by를 설정
        user = self.request.user if getattr(self.request, 'user', None) and self.request.user.is_authenticated else None
        try:
            # try to set both if model/serializer accept them
            serializer.save(created_by=user, updated_by=user)
        except TypeError:
            # fallback to plain save for backward compatibility
            serializer.save()

    def perform_update(self, serializer):
        instance = self.get_object()
        facility = serializer.validated_data.get('facility', instance.facility)
        name = serializer.validated_data.get('name', instance.name)
        # 업데이트 시에도 중복 체크 (자기 자신은 제외)
        if facility and name and Zone.objects.filter(facility=facility, name=name).exclude(pk=instance.pk).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'name': '같은 시설에 동일한 구역 이름이 이미 존재합니다.'})
        user = self.request.user if getattr(self.request, 'user', None) and self.request.user.is_authenticated else None
        try:
            serializer.save(updated_by=user)
        except TypeError:
            serializer.save()

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
class CropViewSet(BaseViewSet):
    queryset = Crop.objects.all()
    serializer_class = CropSerializer

# VarietyViewSet: 품종(Variety) 모델의 CRUD API를 제공합니다.
class VarietyViewSet(BaseViewSet):
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
class RecipeProfileViewSet(BaseViewSet):
    # 기본적으로 삭제되지 않은 레시피만 조회
    queryset = RecipeProfile.objects.filter(is_deleted=False).select_related('variety', 'created_by', 'updated_by')\
        .prefetch_related('comments__replies', 'performances', 'ratings', 'steps__item_values')
    serializer_class = RecipeProfileSerializer
    filterset_fields = ['variety__id', 'recipe_name', 'is_active', 'is_deleted']
    ordering_fields = ['order', 'id']
    search_fields = ['recipe_name', 'description']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=False, methods=['get'], url_path=r'by-variety/(?P<variety_id>[^/.]+)')
    def by_variety(self, request, variety_id=None):
        """variety id로 레시피 프로필, 코멘트(요약), 성과(요약), 평점(샘플)을 함께 조회합니다.
        지원 쿼리파라미터:
        - sort: recent|popular (default: recent)
        - comments_limit: int (default:3)
        - comments_sort: recent|popular (default: popular)
        - performances_limit: int (default:5)
        - performances_sort: recent|top_yield (default: recent)
        """
        sort = request.query_params.get('sort', 'recent')
        comments_limit = int(request.query_params.get('comments_limit', 3))
        comments_sort = request.query_params.get('comments_sort', 'popular')
        performances_limit = int(request.query_params.get('performances_limit', 5))
        performances_sort = request.query_params.get('performances_sort', 'recent')

        qs = RecipeProfile.objects.filter(is_deleted=False, variety_id=variety_id)
        # annotate for popularity sort
        qs = qs.annotate(_avg_rating=Avg('ratings__rating'), _rating_count=Count('ratings'))
        if sort == 'popular':
            qs = qs.order_by('-_avg_rating', '-_rating_count', '-created_at')
        else:
            qs = qs.order_by('-created_at')

        # prefetch related to avoid N+1
        qs = qs.prefetch_related('steps__item_values', 'steps__item_values__control_item')

        page = self.paginate_queryset(qs)
        items = page if page is not None else list(qs)

        results = []
        for profile in items:
            # base serialization without related heavy lists
            base_serialized = RecipeProfileSerializer(profile).data

            # comments limited with sorting
            # annotate using a non-conflicting name to avoid colliding with the model's @property 'helpful_count'
            comments_qs = profile.comments.all().annotate(helpful_count_ann=Count('votes', filter=Q(votes__is_helpful=True)))
            if comments_sort == 'recent':
                comments_qs = comments_qs.order_by('-created_at')
            else:
                comments_qs = comments_qs.order_by('-helpful_count_ann', '-created_at')
            total_comments = comments_qs.count()
            comments_sample = comments_qs[:comments_limit]
            # serialize comments; serializer can still access the model property 'helpful_count' if needed
            base_serialized['comments'] = RecipeCommentSerializer(comments_sample, many=True).data
            base_serialized['comments_pagination'] = {
                'full_list_url': f"/agriseed/recipe-comments/?recipe={profile.id}&ordering={'-helpful_count_ann,-created_at' if comments_sort!='recent' else '-created_at'}",
                'total': total_comments
            }

            # performances limited with sorting
            performances_qs = profile.performances.all()
            if performances_sort == 'top_yield':
                performances_qs = performances_qs.order_by('-yield_amount', '-created_at')
            else:
                performances_qs = performances_qs.order_by('-created_at')
            total_performances = performances_qs.count()
            performances_sample = performances_qs[:performances_limit]
            base_serialized['performances'] = RecipePerformanceSerializer(performances_sample, many=True).data
            base_serialized['performances_pagination'] = {
                'full_list_url': f"/agriseed/recipe-performances/?recipe={profile.id}&ordering={'-yield_amount' if performances_sort=='top_yield' else '-created_at'}",
                'total': total_performances
            }

            # ratings sample (latest few)
            ratings_sample = profile.ratings.order_by('-created_at')[:5]
            base_serialized['ratings'] = RecipeRatingSerializer(ratings_sample, many=True).data

            # aggregated fields are computed properties on model; ensure they are included
            base_serialized['average_rating'] = profile.average_rating
            base_serialized['rating_count'] = profile.rating_count
            base_serialized['average_yield'] = profile.average_yield
            base_serialized['success_rate'] = profile.success_rate

            results.append(base_serialized)

        if page is not None:
            return self.get_paginated_response(results)
        return Response(results)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

class ControlItemViewSet(viewsets.ModelViewSet):
    queryset = ControlItem.objects.all()
    serializer_class = ControlItemSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['item_name', 'scada_tag_name']
    ordering_fields = ['id', 'item_name', 'description', 'scada_tag_name', 'order']

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

class RecipeCommentViewSet(viewsets.ModelViewSet):
    queryset = RecipeComment.objects.all()
    serializer_class = RecipeCommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class RecipeCommentVoteViewSet(viewsets.ModelViewSet):
    queryset = RecipeCommentVote.objects.all()
    serializer_class = RecipeCommentVoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class RecipePerformanceViewSet(viewsets.ModelViewSet):
    """RecipePerformance 모델의 CRUD API"""
    queryset = RecipePerformance.objects.all()
    serializer_class = RecipePerformanceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['recipe__id', 'user__id']
    ordering_fields = ['created_at', 'yield_amount', 'id']

    def perform_create(self, serializer):
        recipe = serializer.validated_data.get('recipe')
        if not recipe:
            from .models import RecipeProfile
            recipe = RecipeProfile.objects.get(pk=1)
        serializer.save(user=self.request.user, recipe=recipe)

class RecipeRatingViewSet(viewsets.ModelViewSet):
    """RecipeRating 모델의 CRUD API"""
    queryset = RecipeRating.objects.all()
    serializer_class = RecipeRatingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['recipe__id', 'user__id']
    ordering_fields = ['created_at', 'rating', 'id']

    def perform_create(self, serializer):
        recipe = serializer.validated_data.get('recipe')
        if not recipe:
            from .models import RecipeProfile
            recipe = RecipeProfile.objects.get(pk=1)
        serializer.save(user=self.request.user, recipe=recipe)

# Tree 및 Tree_tags ViewSet 추가
class TreeViewSet(BaseViewSet):
    """Tree 모델의 CRUD API"""
    # 모델에 정의된 필드 기준으로 필터/검색/정렬 구성
    queryset = Tree.objects.select_related('variety', 'zone').prefetch_related('tags').all()
    serializer_class = TreeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # degree, height_level이 Tree_tags로 이동했으므로 관련 필드로 필터링하도록 변경
    filterset_fields = ['zone__id', 'variety__id', 'tree_code', 'is_deleted', 'tags__degree', 'tags__height_level', 'tags__is_post_harvest', 'tags__has_farm_log']
    # 검색에서 degree 제거 (tags 관련 검색은 tree-tags 엔드포인트 사용 권장)
    search_fields = ['tree_code', 'notes']
    # 정렬 필드에서 degree 제거
    ordering_fields = ['id', 'created_at', 'updated_at', 'tree_age']

# QR payload 복잡 필터 지원을 위한 FilterSet
class TreeTagsFilter(df_filters.FilterSet):
    qr_payload_contains = df_filters.CharFilter(field_name='qr_payload', lookup_expr='icontains')
    # degree는 숫자 필터로, height_level은 문자열 필터로 노출
    degree = df_filters.NumberFilter(field_name='degree')
    height_level = df_filters.CharFilter(field_name='height_level', lookup_expr='iexact')
    # 수확 상태는 단일 boolean으로 제공
    is_post_harvest = df_filters.BooleanFilter(field_name='is_post_harvest')
    has_farm_log = df_filters.BooleanFilter(field_name='has_farm_log')

    class Meta:
        model = Tree_tags
        fields = ['tree', 'barcode_type', 'barcode_value', 'is_active', 'qr_payload_contains', 'degree', 'height_level', 'is_post_harvest', 'has_farm_log']


class TreeTagsViewSet(viewsets.ModelViewSet):
    """Tree_tags 모델의 CRUD API"""
    queryset = Tree_tags.objects.all()
    serializer_class = TreeTagsSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_class = TreeTagsFilter
    search_fields = ['barcode_value', 'qr_payload', 'height_level', 'degree']
    ordering_fields = ['id', 'issue_date', 'created_at']

# TreeImage 및 SpecimenData ViewSet 추가
class TreeImageViewSet(BaseViewSet):
    """TreeImage 모델의 CRUD API (이미지 업로드 포함)"""
    queryset = TreeImage.objects.all()
    serializer_class = TreeImageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['tree__id', 'is_deleted']
    ordering_fields = ['uploaded_at', 'id']

class SpecimenDataViewSet(BaseViewSet):
    """SpecimenData 모델의 CRUD API"""
    queryset = SpecimenData.objects.all()
    serializer_class = SpecimenDataSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    # 모델 컬럼 변경 반영: specimen_code 필드 제거되어 관련 필터/검색어를 제거
    filterset_fields = ['tree__id', 'collected_by', 'is_deleted', 'is_post_harvest', 'sample_type']
    search_fields = ['notes', 'sample_type']
    ordering_fields = ['created_at', 'id']

    def perform_create(self, serializer):
        # 기본 저장은 serializer에 위임
        specimen = serializer.save(collected_by=self.request.user if self.request.user.is_authenticated else None)
        # 파일 업로드 처리: multipart form-data에서 'attachments'로 다중 파일 전송
        files = self.request.FILES.getlist('attachments')
        for f in files:
            content_type = getattr(f, 'content_type', '')
            is_image = content_type.startswith('image/') if content_type else False
            SpecimenAttachment.objects.create(
                specimen=specimen,
                file=f,
                filename=getattr(f, 'name', None),
                content_type=content_type,
                is_image=is_image
            )

    def create(self, request, *args, **kwargs):
        # serializer로 데이터 검증 후 perform_create 호출
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_update(self, serializer):
        specimen = serializer.save()
        # 업데이트 시에도 새로운 파일이 있으면 추가로 저장
        files = self.request.FILES.getlist('attachments')
        for f in files:
            content_type = getattr(f, 'content_type', '')
            is_image = content_type.startswith('image/') if content_type else False
            SpecimenAttachment.objects.create(
                specimen=specimen,
                file=f,
                filename=getattr(f, 'name', None),
                content_type=content_type,
                is_image=is_image
            )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='upload-attachments')
    def upload_attachments(self, request, pk=None):
        """별도 엔드포인트로 파일만 업로드할 때 사용. multipart/form-data, key='attachments'"""
        specimen = self.get_object()
        files = request.FILES.getlist('attachments')
        created = []
        for f in files:
            content_type = getattr(f, 'content_type', '')
            is_image = content_type.startswith('image/') if content_type else False
            att = SpecimenAttachment.objects.create(
                specimen=specimen,
                file=f,
                filename=getattr(f, 'name', None),
                content_type=content_type,
                is_image=is_image
            )
            created.append(SpecimenAttachmentSerializer(att, context={'request': request}).data)
        return Response({'created': created}, status=status.HTTP_201_CREATED)

class SpecimenAttachmentViewSet(BaseViewSet):
    """SpecimenAttachment 모델의 CRUD API (파일별 조회/삭제 등)"""
    queryset = SpecimenAttachment.objects.select_related('specimen').all()
    serializer_class = SpecimenAttachmentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['specimen', 'is_image', 'is_deleted']
    search_fields = ['filename']
    ordering_fields = ['uploaded_at', 'id']

    def perform_create(self, serializer):
        # 파일 업로드은 인증된 사용자만 허용하도록 만들 수 있음
        user = self.request.user if getattr(self.request, 'user', None) and self.request.user.is_authenticated else None
        # specimen field is expected to be provided in request data
        serializer.save()

class SensorItemViewSet(BaseViewSet):
    """SensorItem 모델의 CRUD API"""
    queryset = SensorItem.objects.select_related('item_name').all()
    serializer_class = SensorItemSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['item_name']
    search_fields = ['description', 'item_name__name']
    ordering_fields = ['id']

class MeasurementItemViewSet(BaseViewSet):
    """MeasurementItem 모델의 CRUD API"""
    # MeasurementItem 모델은 sensor_item/is_active 필드를 가지지 않음
    queryset = MeasurementItem.objects.select_related('item_name').all()
    serializer_class = MeasurementItemSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['item_name']
    search_fields = ['description', 'item_name__name']
    ordering_fields = ['id']

class VarietyDataThresholdViewSet(BaseViewSet):
    """품종별 데이터 임계값 CRUD API
    - 권한: 읽기 공개, 작성/수정은 인증 필요
    - 필터: variety, data_name, is_active, level_label, quality_label
    - 검색: note, data_name__name, variety__name, level_label, quality_label
    - 정렬: 우선순위 기준 기본(-priority)
    """
    queryset = VarietyDataThreshold.objects.select_related('variety', 'data_name').all()
    serializer_class = VarietyDataThresholdSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['variety', 'data_name', 'is_active', 'level_label', 'quality_label']
    search_fields = ['note', 'data_name__name', 'variety__name', 'level_label', 'quality_label']
    ordering_fields = ['-priority', 'id', 'created_at']

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
        except IntegrityError:
            return Response({'detail': 'threshold with same variety/data_name/priority already exists'}, status=status.HTTP_400_BAD_REQUEST)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        # 기본 저장
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

class QualityEventViewSet(BaseViewSet):
    """평가 이벤트 로그 조회/관리 API"""
    queryset = QualityEvent.objects.select_related('variety', 'data_name', 'rule').all()
    serializer_class = QualityEventSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['variety', 'data_name', 'level_name', 'quality', 'source_type']
    search_fields = ['message', 'data_name__name', 'variety__name']
    ordering_fields = ['-created_at', 'level_severity']

class EvaluateMeasurementView(APIView):
    """POST로 측정값을 전달하면 품종별 규칙을 찾아 평가하고 QualityEvent를 생성합니다."""
    permission_classes = [permissions.AllowAny]

    # 기존 매핑에 risk/high_risk를 추가하여 평가 단계별 level_name 및 severity를 명확히 함
    LEVEL_MAP = {
        'normal': ('NORMAL', 0),
        'info': ('INFO', 1),
        'warning': ('WARNING', 1),
        'risk': ('WARNING', 2),
        'high_risk': ('CRITICAL', 3),
        'critical': ('CRITICAL', 3),
    }

    def post(self, request, *args, **kwargs):
        serializer = EvaluateMeasurementInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data_name_id = data.get('data_name')
        variety_id = data.get('variety')
        value = data.get('value')
        source_type = data.get('source_type') or 'unknown'
        source_id = data.get('source_id')

        # 데이터명/품종 존재 확인
        try:
            dn = DataName.objects.get(pk=data_name_id)
        except DataName.DoesNotExist:
            return Response({'detail': 'data_name not found'}, status=status.HTTP_400_BAD_REQUEST)

        variety = None
        if variety_id:
            try:
                variety = Variety.objects.get(pk=variety_id)
            except Variety.DoesNotExist:
                return Response({'detail': 'variety not found'}, status=status.HTTP_400_BAD_REQUEST)

        # 규칙 조회: 품종이 주어지면 해당 품종 우선, 없으면 전체에서 data_name 매칭된 것 검색
        rules_qs = VarietyDataThreshold.objects.filter(data_name=dn, is_active=True)
        if variety:
            rules_qs = rules_qs.filter(variety=variety)
        rules_qs = rules_qs.order_by('-priority')

        if not rules_qs.exists():
            return Response({'detail': 'no threshold rule found for given data_name/variety'}, status=status.HTTP_404_NOT_FOUND)

        # 첫 번째 규칙 적용 (우선순위 높은 규칙)
        rule = rules_qs.first()
        eval_result = rule.evaluate(value)
        level_key = eval_result.get('level')
        quality = eval_result.get('quality')
        level_name, severity = self.LEVEL_MAP.get(level_key, ('INFO', 1))

        # 메시지 생성 (간단한 템플릿)
        msg = f"{dn.name}: {level_name} (value={value})"
        if rule.min_good is not None and rule.max_good is not None:
            msg += f"; normal={rule.min_good}~{rule.max_good}"
        if rule.min_warn is not None and rule.max_warn is not None:
            msg += f"; warn={rule.min_warn}~{rule.max_warn}"

        # 이벤트 저장
        event = QualityEvent.objects.create(
            source_type=source_type,
            source_id=source_id,
            variety=variety,
            data_name=dn,
            value=value,
            level_name=level_name,
            level_severity=severity,
            quality=quality,
            rule=rule,
            message=msg
        )

        return Response({
            'data_name': dn.name,
            'variety': str(variety) if variety else None,
            'value': value,
            'level': level_name,
            'severity': severity,
            'quality': quality,
            'rule': rule.id,
            'message': msg,
            'event_id': event.id
        }, status=status.HTTP_200_OK)

# CalendarEvent 및 TodoItem 관련 ViewSet 추가
class CalendarEventViewSet(BaseViewSet):
    metadata_class = StyleMetadata
    """캘린더 이벤트 CRUD API
    - 읽기: 공개, 쓰기(생성/수정/삭제): 인증 필요
    - 필터: facility, created_by, 시작/종료, all_day
    """
    queryset = CalendarEvent.objects.select_related('facility', 'zone', 'created_by').prefetch_related('attendees').all()
    serializer_class = CalendarEventSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, CreatedByOrStaffPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['facility', 'zone', 'created_by', 'all_day', 'is_deleted']
    search_fields = ['title', 'description']
    ordering_fields = ['start', 'end', 'created_at']

    def get_view_name(self):
        return "Calendar Event List"

    def get_view_description(self, html=False):
        return "캘린더 이벤트 CRUD API\n- 읽기: 공개, 쓰기(생성/수정/삭제): 인증 필요\n- 필터: facility, created_by, 시작/종료, all_day"

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)

    # object-level permissions (수정/삭제 허용 여부)는 CreatedByOrStaffPermission이 처리합니다.

class TodoItemViewSet(BaseViewSet):
    metadata_class = StyleMetadata
    """할일(Todo) 모델 CRUD API
    - 읽기: 공개, 쓰기: 인증 필요
    - 추가 액션: 완료 처리(mark_complete)
    """
    queryset = TodoItem.objects.select_related('facility', 'zone', 'assigned_to', 'created_by').all()
    serializer_class = TodoItemSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['facility', 'zone', 'assigned_to', 'created_by', 'completed', 'status', 'priority', 'is_deleted']
    search_fields = ['title', 'description']
    ordering_fields = ['due_date', 'priority', 'created_at']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def mark_complete(self, request, pk=None):
        """특정 Todo를 완료로 표시합니다. 완료 시간을 기록하고 필요시 담당자 할당을 업데이트합니다."""
        instance = self.get_object()
        try:
            instance.mark_complete(by_user=request.user)
        except Exception:
            return Response({'detail': 'failed to mark complete'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(instance).data)

# views.py
import io
import qrcode
from django.http import HttpResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required  # 필요시

@require_GET
# @login_required  # 인증 필요 시 활성화
def qr_image(request, identifier):
    """
    identifier: sample id 또는 sample code
    반환: image/png (QR에는 앱 내 절대 URL 또는 JSON 페이로드 삽입)
    """
    payload = {
        "id": identifier,
        "url": request.build_absolute_uri(f"/measurement/{identifier}"),
        "code": str(identifier)
    }
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(json.dumps(payload))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return HttpResponse(buf.getvalue(), content_type="image/png")

class RecipeByZoneViewSet(viewsets.ReadOnlyModelViewSet):
    """CalendarSchedule 기준으로 zone/facility별 레시피 요약을 반환하는 읽기 전용 ViewSet.
    - Serializer: RecipeByZoneSerializer (읽기 전용, 계산 필드 포함)
    - 필터: facility, zone, crop, variety, recipe_profile, enabled, completed
    - 정렬: id, sowing_date, expected_harvest_date
    """
    queryset = CalendarSchedule.objects.select_related('facility', 'zone', 'crop', 'variety', 'recipe_profile')
    serializer_class = RecipeByZoneSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['facility', 'zone', 'crop', 'variety', 'recipe_profile', 'enabled', 'completed']
    ordering_fields = ['id', 'sowing_date', 'expected_harvest_date']
    search_fields = ['facility__name', 'zone__name', 'crop__name', 'variety__name', 'recipe_profile__recipe_name']

    def get_queryset(self):
        # Prefetch heavy relations for serialization: recipe_profile -> steps -> item_values -> control_item
        qs = super().get_queryset().all()
        qs = qs.prefetch_related('recipe_profile__steps__item_values__control_item')
        return qs

    def list(self, request, *args, **kwargs):
        """기본 list 구현: 페이징 적용 후 RecipeByZoneSerializer로 직렬화하여 반환."""
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class LocationGroupViewSet(viewsets.ModelViewSet):
    """지역 그룹(LocationGroup) 모델의 CRUD API"""
    queryset = LocationGroup.objects.all()
    serializer_class = LocationGroupSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['group_id', 'group_name']
    ordering_fields = ['group_id', 'group_name']

class LocationCodeViewSet(viewsets.ModelViewSet):
    """그룹별 코드(LocationCode) 모델의 CRUD API"""
    queryset = LocationCode.objects.all()
    serializer_class = LocationCodeSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['group__group_id', 'code_type', 'code_key']
    ordering_fields = ['code_id', 'code_type', 'code_key']
    

class ModuleFilter(df_filters.FilterSet):
    # allow API clients to filter by ?facility=<id> while model field is 'facilitys'
    facility = df_filters.NumberFilter(field_name='facilitys')

    class Meta:
        model = Module
        fields = ['facility', 'is_enabled']

class ModuleViewSet(viewsets.ModelViewSet):
    """Module(서브시스템) 모델 CRUD API (agriseed.models.Module)"""
    # facilitys(FK)가 모델에 추가되어 select_related로 조인하여 조회 최적화
    # devices 역참조(DeviceInstance)를 미리 가져오도록 Prefetch 설정
    queryset = Module.objects.select_related('facilitys').prefetch_related(
        Prefetch(
            'devices',
            queryset=DeviceInstance.objects.select_related('device', 'adapter', 'memory_groups')
        )
    ).all()
    serializer_class = ModuleSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    # expose friendly API filter 'facility' mapped by ModuleFilter
    filterset_class = ModuleFilter
    ordering_fields = ['id', 'order', 'name']
    # facilitys__name 으로 검색 가능하게 확장
    search_fields = ['name', 'description', 'facilitys__name']
    
class DeviceInstanceViewSet(viewsets.ModelViewSet):
    """DeviceInstance(설치 장비) 모델 CRUD API (agriseed.models.DeviceInstance)

    추가 기능:
    - POST /agriseed/device-instances/{pk}/ping/ : 단일 디바이스 last_seen 갱신
      Body (선택): {"status":"active"}
    - POST /agriseed/device-instances/ping/ : serial_number 리스트로 벌크 갱신
      Body: {"serial_numbers":["SN-001","SN-002"], "status":"active"}
    """
    # memory_groups is a FK -> use select_related; control_groups/calc_groups are M2M so prefetch
    queryset = DeviceInstance.objects.select_related('device', 'module', 'adapter', 'memory_groups').all()
    serializer_class = DeviceInstanceSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['device', 'adapter', 'module', 'status', 'is_active']
    ordering_fields = ['last_seen', 'id']
    search_fields = ['serial_number', 'name']

    @action(detail=True, methods=['post'], url_path='ping')
    def ping(self, request, pk=None):
        """단일 장치 ping -> last_seen(now) 및 (선택) status 갱신"""
        inst = self.get_object()
        now = timezone.now()
        fields_to_update = ['last_seen']
        inst.last_seen = now
        new_status = request.data.get('status')
        if isinstance(new_status, str) and new_status.strip():
            inst.status = new_status.strip()
            fields_to_update.append('status')
        inst.save(update_fields=fields_to_update)
        return Response({
            'id': inst.id,
            'serial_number': inst.serial_number,
            'last_seen': inst.last_seen.isoformat(),
            'status': inst.status,
            'updated_fields': fields_to_update
        })

    @action(detail=False, methods=['post'], url_path='ping')
    def ping_bulk(self, request):
        """여러 serial_number를 한번에 ping.
        Body 예: {"serial_numbers":["SN-001","SN-002"], "status":"active"}
        """
        serials = request.data.get('serial_numbers') or []
        if not isinstance(serials, list) or not serials:
            return Response({'detail': 'serial_numbers 리스트가 필요합니다.'}, status=400)
        new_status = request.data.get('status')
        now = timezone.now()
        updated = []
        for sn in serials:
            try:
                inst = DeviceInstance.objects.get(serial_number=sn)
                inst.last_seen = now
                fields = ['last_seen']
                if isinstance(new_status, str) and new_status.strip():
                    inst.status = new_status.strip()
                    fields.append('status')
                inst.save(update_fields=fields)
                updated.append({
                    'serial_number': sn,
                    'id': inst.id,
                    'last_seen': inst.last_seen.isoformat(),
                    'status': inst.status,
                    'updated_fields': fields
                })
            except DeviceInstance.DoesNotExist:
                updated.append({'serial_number': sn, 'error': 'not found'})
        return Response({'updated': updated, 'count': len(updated)})