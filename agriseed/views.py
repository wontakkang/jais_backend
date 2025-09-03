from rest_framework import viewsets
from .models import *
from .serializers import *
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from django.db.models import Count, Avg, Q
from rest_framework.pagination import PageNumberPagination
from django_filters import rest_framework as df_filters

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
            comments_qs = profile.comments.all().annotate(helpful_count=Count('votes', filter=Q(votes__is_helpful=True)))
            if comments_sort == 'recent':
                comments_qs = comments_qs.order_by('-created_at')
            else:
                comments_qs = comments_qs.order_by('-helpful_count', '-created_at')
            total_comments = comments_qs.count()
            comments_sample = comments_qs[:comments_limit]
            base_serialized['comments'] = RecipeCommentSerializer(comments_sample, many=True).data
            base_serialized['comments_pagination'] = {
                'full_list_url': f"/agriseed/recipe-comments/?recipe={profile.id}&ordering={'-helpful_count,-created_at' if comments_sort!='recent' else '-created_at'}",
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
    filterset_fields = ['zone__id', 'variety__id', 'tree_code', 'is_deleted']
    search_fields = ['tree_code', 'notes', 'degree']
    ordering_fields = ['id', 'created_at', 'updated_at', 'tree_age', 'degree']

# QR payload 복잡 필터 지원을 위한 FilterSet
class TreeTagsFilter(df_filters.FilterSet):
    qr_payload_contains = df_filters.CharFilter(field_name='qr_payload', lookup_expr='icontains')

    class Meta:
        model = Tree_tags
        fields = ['tree', 'barcode_type', 'barcode_value', 'is_active', 'qr_payload_contains']

class TreeTagsViewSet(viewsets.ModelViewSet):
    """Tree_tags 모델의 CRUD API"""
    queryset = Tree_tags.objects.all()
    serializer_class = TreeTagsSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_class = TreeTagsFilter
    search_fields = ['barcode_value', 'qr_payload']
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
    filterset_fields = ['tree__id', 'specimen_code', 'collected_by', 'is_deleted']
    search_fields = ['specimen_code', 'notes', 'sample_type']
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
