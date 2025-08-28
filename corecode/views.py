from django.shortcuts import render
from rest_framework import viewsets, filters, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction, IntegrityError
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.renderers import JSONRenderer
import logging
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from .models import *
from .serializers import *
from utils.custom_permission import LocalhostBypassPermission
from django.contrib.auth import get_user_model
from django.apps import apps

logger = logging.getLogger('corecode')

# ProjectViewSet
# -------------------
# 이 ViewSet은 프로젝트의 CRUD, 버전 백업(코멘트와 함께 저장), 특정 버전으로의 복구(롤백) 기능을 제공합니다.
# 주요 기능:
#   - 프로젝트 생성/조회/수정/삭제
#   - /projects/{id}/backup/ : 현재 상태를 ProjectVersion으로 저장(코멘트, 버전명 포함)
#   - /projects/{id}/restore/{version_id}/ : 특정 버전의 상태로 복구(롤백)
#   - ProjectVersion, MemoryGroup, Variable 모델과 연동하여 전체 메모리 맵 구조를 관리
#   - git과 유사한 프로젝트 이력 관리 및 복구 지원
#
# 사용 예시:
#   POST /projects/1/backup/ {"note": "설명", "version": "버전명"}
#   POST /projects/1/restore/3/ (3번 버전으로 복구)
# -------------------
#
# ProjectVersionViewSet, MemoryGroupViewSet, VariableViewSet은 각각의 모델에 대한 CRUD API를 제공합니다.
# -------------------
# ProjectVersionViewSet: 프로젝트 버전(ProjectVersion) 모델의 CRUD API를 제공합니다.
# MemoryGroupViewSet: 메모리 그룹(MemoryGroup) 모델의 CRUD API를 제공합니다.
# VariableViewSet: 변수(Variable) 모델의 CRUD API를 제공합니다.
# -------------------

# Create your views here.

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

    def perform_create(self, serializer):
        project = serializer.save()
        version = self.request.data.get("versions")
        if version:
            # ProjectVersion 생성 (groups는 직접 할당 X)
            pv = ProjectVersion.objects.create(
                project=project,
                note=version['note'],
                version=version['version']
            )
            # groups와 variables를 별도로 생성
            for group_data in version.get('groups', []):
                variables_data = group_data.pop('variables', [])
                group_data.pop('project_version', None)  # 중복 방지
                group_data.pop('id', None)  # id 필드 제거
                group = MemoryGroup.objects.create(project_version=pv, **group_data)
                for var_data in variables_data:
                    var_data.pop('group', None)  # 중복 방지
                    var_data.pop('id', None)     # id도 제거
                    var_data.pop('device_address', None)  # 존재하지 않는 필드 제거
                    Variable.objects.create(group=group, **var_data)
        return project

class ProjectVersionViewSet(viewsets.ModelViewSet):
    """
    프로젝트 버전(ProjectVersion) 모델의 CRUD 및 복구/스냅샷 관리 API
    - create: 버전 생성 시 해당 시점의 MemoryGroup/Variable 전체 복사
    - restore_version: 해당 버전의 MemoryGroup/Variable을 현재로 복원
    """
    queryset = ProjectVersion.objects.all()
    serializer_class = ProjectVersionSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['project__id']
    ordering_fields = ['id', 'updated_at']

class ProjectVersionRestoreView(APIView):
    def post(self, request, project_id, version):
        try:
            project = Project.objects.get(id=project_id)
            pv = ProjectVersion.objects.get(project=project, version=version)
            pv.restore_version()
            pv.save()  # updated_at 갱신
            return Response({'detail': '복구 완료'}, status=status.HTTP_200_OK)
        except Project.DoesNotExist:
            return Response({'detail': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)
        except ProjectVersion.DoesNotExist:
            return Response({'detail': 'ProjectVersion not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class UserPreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    def _resolve_user_for_pref(self, username):
        """Return the User model instance using get_user_model()."""
        UserModel = get_user_model()
        return UserModel.objects.filter(username=username)[0]

    def get(self, request, username):
        if request.user.username != username:
            return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            user_obj = self._resolve_user_for_pref(username)
            pref, _ = UserPreference.objects.get_or_create(user_id=user_obj.id)
            serializer = UserPreferenceSerializer(pref)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, username):
        if request.user.username != username:
            return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            user_obj = self._resolve_user_for_pref(username)
            pref, _ = UserPreference.objects.get_or_create(user=user_obj)
            serializer = UserPreferenceSerializer(pref, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, username):
        if request.user.username != username:
            return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            user_obj = self._resolve_user_for_pref(username)
            pref, _ = UserPreference.objects.get_or_create(user=user_obj)
            serializer = UserPreferenceSerializer(pref, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

class UserMeView(APIView):
    permission_classes = [LocalhostBypassPermission]

    def get(self, request):
        user = request.user
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            # 필요시 추가 필드
        })

class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logger.info('Signup attempt from IP %s, data keys: %s', request.META.get('REMOTE_ADDR'), list(request.data.keys()))
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            try:
                tokens_container = {}

                def _make_tokens(user):
                    try:
                        refresh = RefreshToken.for_user(user)
                        tokens_container['access'] = str(refresh.access_token)
                        tokens_container['refresh'] = str(refresh)
                    except Exception as e:
                        logger.exception('Token creation failed in on_commit: %s', str(e))

                try:
                    with transaction.atomic():
                        user = serializer.save()
                        # Ensure token creation happens after DB commit
                        transaction.on_commit(lambda: _make_tokens(user))
                except serializers.ValidationError as ve:
                    logger.warning('Signup validation failed at create: %s', ve.detail)
                    return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
                except IntegrityError as ie:
                    logger.exception('Signup IntegrityError during create: %s', str(ie))
                    return Response({'detail': 'Database integrity error'}, status=status.HTTP_400_BAD_REQUEST)
                except Exception as e:
                    logger.exception('Signup error during create: %s', str(e))
                    return Response({'detail': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # transaction.on_commit callbacks should have run by now; check tokens
                if tokens_container:
                    logger.info('Signup success for username=%s id=%s', user.username, user.id)
                    return Response({
                        'id': user.id,
                        'username': user.username,
                        'access': tokens_container.get('access'),
                        'refresh': tokens_container.get('refresh')
                    }, status=status.HTTP_201_CREATED)
                else:
                    logger.warning('Signup succeeded but token not issued for username=%s', user.username)
                    return Response({
                        'id': user.id,
                        'username': user.username,
                        'detail': 'User created but token issuance failed or not available. Please login to obtain tokens.'
                    }, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.exception('Unhandled signup error: %s', str(e))
                return Response({'detail': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            logger.warning('Signup validation failed: %s', serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UsersListView(APIView):
    """Debug endpoint to list users. Enabled only in DEBUG or when accessed from localhost."""
    permission_classes = [LocalhostBypassPermission]

    def get(self, request):
        if not settings.DEBUG and request.META.get('REMOTE_ADDR') not in ('127.0.0.1', '::1'):
            return Response({'detail': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
        UserModel = get_user_model()
        users = UserModel.objects.all().values('id', 'username', 'email', 'is_active', 'is_staff', 'is_superuser')
        return Response(list(users))

class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['manufacturer', 'user_manuals']
    ordering_fields = ['id', 'name', 'created_at']

class DeviceCompanyViewSet(viewsets.ModelViewSet):
    queryset = DeviceCompany.objects.all()
    serializer_class = DeviceCompanySerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['name']
    ordering_fields = ['id', 'name']

class UserManualViewSet(viewsets.ModelViewSet):
    queryset = UserManual.objects.all()
    serializer_class = UserManualSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['title']
    ordering_fields = ['id', 'title', 'uploaded_at']

class DataNameViewSet(viewsets.ModelViewSet):
    queryset = DataName.objects.all()
    serializer_class = DataNameSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def dict(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = {str(obj['id']): obj for obj in serializer.data}
        return Response(data)

class ControlValueViewSet(viewsets.ModelViewSet):
    queryset = ControlValue.objects.all()
    serializer_class = ControlValueSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'command_name', 'target', 'data_type', 'control_user']
    ordering_fields = ['id', 'created_at', 'updated_at', 'control_at']

class ControlValueHistoryViewSet(viewsets.ModelViewSet):
    queryset = ControlValueHistory.objects.all()
    serializer_class = ControlValueHistorySerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'command_name', 'target', 'data_type', 'control_value']
    ordering_fields = ['id', 'created_at', 'control_at']

class VariableViewSet(viewsets.ModelViewSet):
    """
    변수(Variable) 모델의 CRUD API를 제공합니다.
    각 Variable 인스턴스는 group 필드를 통해 MemoryGroup과 연결되어 있습니다.
    """
    queryset = Variable.objects.all()
    serializer_class = VariableSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['group__id']
    ordering_fields = ['id']
    
class MemoryGroupViewSet(viewsets.ModelViewSet):
    """
    메모리 그룹(MemoryGroup) 모델의 CRUD API를 제공합니다.
    각 MemoryGroup 인스턴스는 project_version 필드를 통해 ProjectVersion(프로젝트 버전)과 연결되어 있습니다.
    """
    queryset = MemoryGroup.objects.all()
    serializer_class = MemoryGroupSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['project_version__id']
    ordering_fields = ['id']
    
class CalcVariableViewSet(viewsets.ModelViewSet):
    queryset = CalcVariable.objects.all()
    serializer_class = CalcVariableSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['group__id']
    ordering_fields = ['id']

class CalcGroupViewSet(viewsets.ModelViewSet):
    queryset = CalcGroup.objects.all()
    serializer_class = CalcGroupSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['project_version__id']
    ordering_fields = ['id']

class ControlLogicViewSet(viewsets.ModelViewSet):
    queryset = ControlLogic.objects.all()
    serializer_class = ControlLogicSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['use_method'] # group__id 제거, 모델 필드에 맞게 수정
    ordering_fields = ['id']

    @action(detail=False, methods=['get'])
    def dict(self, request):
        """
        Return control logics as dict (default) or list (if ?type=list).
        """
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        if request.query_params.get('type') == 'list':
            return Response(data)
        # default: return dict keyed by id
        result = {str(item['id']): item for item in data}
        return Response(result)

class ControlVariableViewSet(viewsets.ModelViewSet):
    queryset = ControlVariable.objects.all()
    serializer_class = ControlVariableSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['group__id', 'name__id', 'applied_logic__id']
    ordering_fields = ['id']

class ControlGroupViewSet(viewsets.ModelViewSet):
    queryset = ControlGroup.objects.all()
    serializer_class = ControlGroupSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['project_version__id']
    ordering_fields = ['id']

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
