import glob
import os
import re
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from rest_framework import viewsets, filters, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction, IntegrityError
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
import logging
from utils.ws_log import LOG_DIR, LOG_GLOB
try:
    from rest_framework_simplejwt.tokens import RefreshToken  # type: ignore
except Exception:
    RefreshToken = None
from django.conf import settings
from .models import *
from .serializers import *
from utils.custom_permission import LocalhostBypassPermission
from django.contrib.auth import get_user_model
logger = logging.getLogger('corecode')


# 모듈 레벨: 로그 디렉터리 통일
LOG_DIR = os.path.join(os.getcwd(), 'log')
LOG_GLOB = os.path.join(LOG_DIR, 'de_mcu*.log')

def list_log_files():
    """Return deduplicated list of .log basenames sorted by mtime desc."""
    try:
        files = glob.glob(os.path.join(LOG_DIR, '*.log'))
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        seen = set()
        names = []
        for p in files:
            n = os.path.basename(p)
            if n in seen:
                continue
            seen.add(n)
            names.append(n)
        return names
    except Exception:
        return []

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


class AdapterViewSet(viewsets.ModelViewSet):
    queryset = Adapter.objects.all()
    serializer_class = AdapterSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['protocol', 'is_deleted']
    ordering_fields = ['id', 'name', 'updated_at']
    search_fields = ['name', 'description']
    
    

# Add UI view for DE-MCU log
def logging_view(request):
    """Render the DE-MCU log UI template with log file list."""
    log_files = list_log_files()
    latest = None
    files = glob.glob(LOG_GLOB)
    if files:
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        latest = os.path.basename(files[0])
    context = {'log_files': log_files, 'selected_log': latest}
    return render(request, 'corecode/logger.html', context)

class LoggingView(APIView):
    """Serve the de_mcu log as an HTML page. Auto-select latest dated file and provide JS-based auto-refresh.
    Query params:
      - lines: int, number of tail lines to show (default 200)
    """

    # Remove class-level LOG_DIR/LOG_GLOB; use module-level LOG_DIR/LOG_GLOB
    LINE_RE = re.compile(r'^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[(?P<level>[^\]]+)\] (?P<msg>.*)$')

    def find_latest_log_file(self):
        p_fixed = os.path.join(LOG_DIR, 'de_mcu.log')
        if os.path.exists(p_fixed):
            return p_fixed
        files = glob.glob(LOG_GLOB)
        if not files:
            return None
        files.sort(key=lambda p: os.getmtime(p), reverse=True)
        return files[0]

    def tail_lines(self, filepath, n=200):
        # Efficient tail: read from end in blocks
        avg_line_size = 200
        to_read = n * avg_line_size
        try:
            with open(filepath, 'rb') as f:
                try:
                    f.seek(0, os.SEEK_END)
                    file_size = f.tell()
                    if file_size == 0:
                        return [], 0
                    # seek back enough bytes
                    seek_pos = max(0, file_size - to_read)
                    f.seek(seek_pos)
                    data = f.read().decode('utf-8', errors='replace')
                    lines = data.splitlines()
                    # if we didn't start at beginning, drop first partial line
                    if seek_pos > 0 and len(lines) > 0:
                        # compute byte offset of the first full line
                        # find the byte index of the first line's start
                        first_line = lines[0]
                        # find in data the boundary
                        idx = data.find(first_line)
                        if idx != -1:
                            start_offset = seek_pos + idx
                        else:
                            start_offset = seek_pos
                        lines = lines[1:]
                    else:
                        start_offset = 0
                except Exception:
                    # fallback to simple read
                    f.seek(0)
                    all_data = f.read().decode('utf-8', errors='replace')
                    lines = all_data.splitlines()
                    start_offset = 0
        except Exception:
            return [], 0
        # Return last n lines and byte offset of the first returned line
        result = lines[-n:]
        # compute actual start offset of result[0]
        if result:
            # find result[0] in file: to avoid re-scanning whole file, approximate from start_offset
            try:
                with open(filepath, 'rb') as f:
                    f.seek(start_offset)
                    chunk = f.read().decode('utf-8', errors='replace')
                    idx = chunk.find(result[0])
                    if idx != -1:
                        start_offset = start_offset + idx
            except Exception:
                pass
        return result, start_offset

    def read_prev_lines(self, filepath, before_offset, n=200):
        # Read up to n lines immediately before the given byte offset (exclusive).
        if before_offset <= 0:
            return [], 0
        avg_line_size = 200
        to_read = n * avg_line_size
        try:
            with open(filepath, 'rb') as f:
                start_seek = max(0, before_offset - to_read)
                f.seek(start_seek)
                data = f.read(before_offset - start_seek).decode('utf-8', errors='replace')
                lines = data.splitlines()
                # If we started mid-line, drop first partial
                if start_seek > 0 and lines:
                    lines = lines[1:]
                # We want the last n lines from this block
                result = lines[-n:]
                # compute byte offset of first returned line
                first = result[0] if result else None
                if first:
                    idx = data.find(first)
                    if idx != -1:
                        return result, start_seek + idx
                return result, start_seek
        except Exception:
            return [], 0

    def get(self, request):
        lines_param = int(request.GET.get('lines', 200))
        latest = self.find_latest_log_file()
        if not latest:
            return HttpResponse('<pre>No log files found.</pre>', content_type='text/html')

        raw_lines, cursor = self.tail_lines(latest, lines_param)
        raw_lines = list(reversed(raw_lines))

        # Render template instead of manual HTML build
        log_files = list_log_files()
        context = {
            'log_files': log_files,
            'selected_log': os.path.basename(latest),
            'lines': lines_param,
        }
        return render(request, 'corecode/logger.html', context)

class LoggerTailView(APIView):
    """Return last N lines as JSON (newest first). Query: ?lines=200&file=basename.log"""
    LINE_RE = LoggingView.LINE_RE

    def find_latest_log_file(self):
        p_fixed = os.path.join(LOG_DIR, 'scheduler.log')
        if os.path.exists(p_fixed):
            return p_fixed
        files = glob.glob(LOG_GLOB)
        if not files:
            return None
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return files[0]

    def tail_lines(self, filepath, n=200):
        return LoggingView.tail_lines(self, filepath, n)

    def _resolve_requested_file(self, basename):
        if not basename:
            return None
        # only allow plain basename without path components
        if os.path.basename(basename) != basename:
            return None
        candidate = os.path.join(LOG_DIR, basename)
        if os.path.exists(candidate) and os.path.isfile(candidate):
            return candidate
        return None

    def get(self, request):
        lines_param = int(request.GET.get('lines', 200))
        before = request.GET.get('before')
        file_param = request.GET.get('file')

        # if client requested specific file, validate and use it
        if file_param:
            chosen = self._resolve_requested_file(file_param)
            if not chosen:
                return JsonResponse({'error': 'Invalid file parameter'}, status=400)
            latest = chosen
        else:
            latest = self.find_latest_log_file()

        if not latest:
            return JsonResponse({'lines': []})

        if before is not None:
            try:
                before_off = int(before)
            except Exception:
                before_off = 0
            raw_lines, start_off = self.read_prev_lines(latest, before_off, lines_param)
            has_more = start_off > 0
        else:
            raw_lines, start_off = self.tail_lines(latest, lines_param)
            has_more = start_off > 0

        raw_lines = list(reversed(raw_lines))
        out = []
        for line in raw_lines:
            m = self.LINE_RE.match(line)
            if m:
                out.append({'ts': m.group('ts'), 'level': m.group('level'), 'msg': m.group('msg')})
            else:
                out.append({'ts': None, 'level': None, 'msg': line})
        return JsonResponse({'lines': out, 'cursor': start_off, 'has_more': has_more})
