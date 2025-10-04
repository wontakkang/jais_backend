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
try:
    from rest_framework_simplejwt.tokens import RefreshToken  # type: ignore
except Exception:
    RefreshToken = None
from django.conf import settings
from .models import *
from .serializers import *
from utils.custom_permission import LocalhostBypassPermission
from django.contrib.auth import get_user_model
from django.apps import apps
from agriseed.models import Module as AgriseedModule, DeviceInstance as AgriseedDeviceInstance
from django.utils import timezone
from agriseed.serializers import ModuleSerializer as AgriseedModuleSerializer

logger = logging.getLogger('corecode')

# Create your views here.

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
                        if RefreshToken:
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


class UsersAdminListView(APIView):
    """Admin endpoint to list users.
    - 권한: 인증 및 staff 계정만 사용 가능
    - 반환: id, username, email, is_active, is_staff
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        UserModel = get_user_model()
        qs = UserModel.objects.all().values('id', 'username', 'email', 'is_active', 'is_staff')
        return Response(list(qs))

class UserIdToUsernameView(APIView):
    """Return username for a given user id.
    Authorization: authenticated users only. Staff can query any user; non-staff can query only their own id.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            UserModel = get_user_model()
            user = UserModel.objects.get(pk=user_id)
        except Exception:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # Authorization: allow if staff or same user
        if not (request.user.is_staff or request.user.id == user.id):
            return Response({'detail': '권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)

        # Return username only
        return Response({'username': user.username})

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

    def get_view_name(self):
        return "Data Name List"

    def get_view_description(self, html=False):
        return "DataName CRUD API"

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
    각 MemoryGroup 인스턴스는 여러 Variable과 연결되어 있습니다.
    """
    queryset = MemoryGroup.objects.all()
    serializer_class = MemoryGroupSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['id', 'name', 'Device', 'Device__name']
    ordering_fields = ['id', 'name']
    
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
    filterset_fields = ['id', 'name']
    ordering_fields = ['id']

class ControlLogicViewSet(viewsets.ModelViewSet):
    queryset = ControlLogic.objects.all()
    serializer_class = ControlLogicSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['use_method'] # 모델 필드에 맞게 구성
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

class ControlGroupViewSet(viewsets.ModelViewSet):
    queryset = ControlGroup.objects.all()
    serializer_class = ControlGroupSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['id', 'name']
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

class ModuleViewSet(viewsets.ModelViewSet):
    """Module(서브시스템) 모델 CRUD API (agriseed.models.Module)"""
    queryset = AgriseedModule.objects.all()
    serializer_class = AgriseedModuleSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['is_enabled']
    ordering_fields = ['id', 'order', 'name']
    search_fields = ['name', 'description']

class DeviceInstanceViewSet(viewsets.ModelViewSet):
    """DeviceInstance(설치 장비) 모델 CRUD API (agriseed.models.DeviceInstance)

    추가 기능:
    - POST /corecode/device-instances/{pk}/ping/ : 단일 디바이스 last_seen 갱신
      Body (선택): {"status":"active"}
    - POST /corecode/device-instances/ping/ : serial_number 리스트로 벌크 갱신
      Body: {"serial_numbers":["SN-001","SN-002"], "status":"active"}
    """
    queryset = AgriseedDeviceInstance.objects.select_related('device', 'module', 'adapter').prefetch_related('memory_groups').all()
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
                inst = AgriseedDeviceInstance.objects.get(serial_number=sn)
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
            except AgriseedDeviceInstance.DoesNotExist:
                updated.append({'serial_number': sn, 'error': 'not found'})
        return Response({'updated': updated, 'count': len(updated)})

class AdapterViewSet(viewsets.ModelViewSet):
    queryset = Adapter.objects.all()
    serializer_class = AdapterSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['protocol', 'is_deleted']
    ordering_fields = ['id', 'name', 'updated_at']
    search_fields = ['name', 'description']
