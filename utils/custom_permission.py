from django.conf import settings
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.authentication import BaseAuthentication
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

class LocalhostBypassPermission(BasePermission):
    def has_permission(self, request, view):
        # 개발용: 모든 요청 허용
        return True

class CustomIPAuthentication(BaseAuthentication):
    def authenticate(self, request):
        """개발 도우미: 모든 요청을 사용자로 인증합니다.
        사용자명 소스 우선순위:
          1. X-Auth-Username 헤더
          2. REMOTE_USER 환경변수
          3. REMOTE_ADDR (IP)를 대체 사용자명으로 사용
        사용자가 존재하지 않으면 사용 불가능한 패스워드로 생성합니다.
        """
        ip = request.META.get('HTTP_X_FORWARDED_FOR')
        if ip:
            ip = ip.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')

        username = request.META.get('HTTP_X_AUTH_USERNAME') or request.META.get('REMOTE_USER') or ip or 'devuser'

        User = get_user_model()
        try:
            user, created = User.objects.get_or_create(username=username, defaults={'email': ''})
            if created:
                # 사용 가능한 패스워드가 없도록 보장
                user.set_unusable_password()
                user.is_active = True
                user.save(update_fields=['password', 'is_active', 'email'])
            return (user, None)
        except Exception:
            return (AnonymousUser(), None)

class CreatedByOrStaffPermission(BasePermission):
    """객체 레벨 권한: 모든 사람에게 안전한 메서드 허용; 안전하지 않은 메서드의 경우,
    request.user가 스태프이거나 obj.created_by가 None이거나 사용자와 같을 때만 허용합니다.
    이는 CalendarEventViewSet.perform_update/destroy의 이전 임시 검사를 반영합니다.
    """
    def has_permission(self, request, view):
        # 뷰 레벨 접근 허용; 객체 레벨 검사가 생성자/스태프 규칙을 강제합니다.
        return True

    def has_object_permission(self, request, view, obj):
        # 모든 사람에게 읽기 전용 메서드 허용
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        if getattr(user, 'is_staff', False):
            return True
        creator = getattr(obj, 'created_by', None)
        # 생성자가 None인 경우 (예: 익명으로 생성된 경우) 수정 허용
        if creator is None or creator == user:
            return True
        return False
