from django.conf import settings
from rest_framework.permissions import BasePermission
from rest_framework.authentication import BaseAuthentication
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

class LocalhostBypassPermission(BasePermission):
    def has_permission(self, request, view):
        # 개발용: 모든 요청 허용
        return True

class CustomIPAuthentication(BaseAuthentication):
    def authenticate(self, request):
        """Development helper: authenticate any request as a user.
        Priority for username source:
          1. X-Auth-Username header
          2. REMOTE_USER env
          3. REMOTE_ADDR (IP) as fallback username
        If the user does not exist, create it with unusable password.
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
                # ensure no usable password
                user.set_unusable_password()
                user.is_active = True
                user.save(update_fields=['password', 'is_active', 'email'])
            return (user, None)
        except Exception:
            return (AnonymousUser(), None)
