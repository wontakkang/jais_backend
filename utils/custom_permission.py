from django.conf import settings
from rest_framework.permissions import BasePermission
from rest_framework.authentication import BaseAuthentication
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

class LocalhostBypassPermission(BasePermission):
    def has_permission(self, request, view):
        ip = request.META.get('REMOTE_ADDR')
        if ip in settings.EXCLUDE_AUTH_IP:
            print(request.META.get('REMOTE_ADDR'))
            return True
        return request.user and request.user.is_authenticated

class CustomIPAuthentication(BaseAuthentication):
    def authenticate(self, request):
        ip = request.META.get('HTTP_X_FORWARDED_FOR')
        if ip:
            ip = ip.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        if ip in settings.EXCLUDE_AUTH_IP:
            User = get_user_model()
            try:
                sysadmin = User.objects.get(username='sysadmin')
                return (sysadmin, None)
            except User.DoesNotExist:
                return (AnonymousUser(), None)
        return None
