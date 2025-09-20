from rest_framework import viewsets, filters, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction, IntegrityError
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
import logging

from corecode.models import (
    Project, ProjectVersion, MemoryGroup, Variable, CalcGroup, CalcVariable,
    ControlGroup, ControlVariable, ControlLogic, Module, DeviceInstance,
    ControlValue, ControlValueHistory, DataName, Device, DeviceCompany, UserManual,
    LocationGroup, LocationCode
)
from agriseed.serializers import (
    ProjectSerializer, ProjectVersionSerializer, MemoryGroupSerializer, VariableSerializer,
    CalcGroupSerializer, CalcVariableSerializer, ControlGroupSerializer, ControlVariableSerializer,
    ControlLogicSerializer, ModuleSerializer, DeviceInstanceSerializer, ControlValueSerializer,
    ControlValueHistorySerializer, DataNameSerializer, DeviceSerializer, DeviceCompanySerializer,
    UserManualSerializer, LocationGroupSerializer, LocationCodeSerializer, SignupSerializer, UserPreferenceSerializer
)
from utils.custom_permission import LocalhostBypassPermission
from django.contrib.auth import get_user_model as django_get_user_model

logger = logging.getLogger('corecode')
User = django_get_user_model()

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

    def perform_create(self, serializer):
        project = serializer.save()
        version = self.request.data.get("versions")
        if version:
            pv = ProjectVersion.objects.create(project=project, note=version.get('note', ''), version=version.get('version', ''))
            for group_data in version.get('groups', []):
                variables_data = group_data.pop('variables', [])
                group_data.pop('project_version', None)
                group_data.pop('id', None)
                group = MemoryGroup.objects.create(project_version=pv, **group_data)
                for var_data in variables_data:
                    var_data.pop('group', None)
                    var_data.pop('id', None)
                    var_data.pop('device_address', None)
                    Variable.objects.create(group=group, **var_data)
        return project

class ProjectVersionViewSet(viewsets.ModelViewSet):
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
            pv.save()
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
        UserModel = get_user_model()
        return UserModel.objects.filter(username=username)[0]

    def get(self, request, username):
        if request.user.username != username:
            return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            user_obj = self._resolve_user_for_pref(username)
            pref, _ = UserPreferenceSerializer.Meta.model.objects.get_or_create(user_id=user_obj.id)
            serializer = UserPreferenceSerializer(pref)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, username):
        if request.user.username != username:
            return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            user_obj = self._resolve_user_for_pref(username)
            pref, _ = UserPreferenceSerializer.Meta.model.objects.get_or_create(user=user_obj)
            serializer = UserPreferenceSerializer(pref, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, username):
        return self.put(request, username)

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
                        transaction.on_commit(lambda: _make_tokens(user))
                except serializers.ValidationError as ve:
                    return Response(ve.detail, status=status.HTTP_400_BAD_REQUEST)
                except IntegrityError as ie:
                    return Response({'detail': 'Database integrity error'}, status=status.HTTP_400_BAD_REQUEST)
                if tokens_container:
                    return Response({'id': user.id, 'username': user.username, 'access': tokens_container.get('access'), 'refresh': tokens_container.get('refresh')}, status=status.HTTP_201_CREATED)
                else:
                    return Response({'id': user.id, 'username': user.username, 'detail': 'User created but token issuance failed or not available. Please login to obtain tokens.'}, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.exception('Unhandled signup error: %s', str(e))
                return Response({'detail': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UsersListView(APIView):
    permission_classes = [LocalhostBypassPermission]

    def get(self, request):
        if not settings.DEBUG and request.META.get('REMOTE_ADDR') not in ('127.0.0.1', '::1'):
            return Response({'detail': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
        UserModel = get_user_model()
        users = UserModel.objects.all().values('id', 'username', 'email', 'is_active', 'is_staff', 'is_superuser')
        return Response(list(users))

class UsersAdminListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        UserModel = get_user_model()
        qs = UserModel.objects.all().values('id', 'username', 'email', 'is_active', 'is_staff')
        return Response(list(qs))

class UserIdToUsernameView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            UserModel = get_user_model()
            user = UserModel.objects.get(pk=user_id)
        except Exception:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        if not (request.user.is_staff or request.user.id == user.id):
            return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        return Response({'username': user.username})

# List-type viewsets for control/project related models
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
    queryset = Variable.objects.all()
    serializer_class = VariableSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['group__id']
    ordering_fields = ['id']

class MemoryGroupViewSet(viewsets.ModelViewSet):
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
    filterset_fields = ['use_method']
    ordering_fields = ['id']

    @action(detail=False, methods=['get'])
    def dict(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        if request.query_params.get('type') == 'list':
            return Response(data)
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
    queryset = LocationGroup.objects.all()
    serializer_class = LocationGroupSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['group_id', 'group_name']
    ordering_fields = ['group_id', 'group_name']

class LocationCodeViewSet(viewsets.ModelViewSet):
    queryset = LocationCode.objects.all()
    serializer_class = LocationCodeSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['group__group_id', 'code_type', 'code_key']
    ordering_fields = ['code_id', 'code_type', 'code_key']

class ModuleViewSet(viewsets.ModelViewSet):
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['facility', 'location_group', 'module_type', 'is_enabled']
    ordering_fields = ['id', 'order', 'name']
    search_fields = ['name', 'description']

class DeviceInstanceViewSet(viewsets.ModelViewSet):
    queryset = DeviceInstance.objects.select_related('catalog', 'module', 'catalog__manufacturer').all()
    serializer_class = DeviceInstanceSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['catalog', 'module', 'status', 'is_active']
    ordering_fields = ['last_seen', 'id']
    search_fields = ['serial_number', 'name', 'device_id', 'mac_address']
