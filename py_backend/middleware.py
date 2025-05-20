from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.conf import settings

class ExcludeJWTForLocalhostMiddleware(MiddlewareMixin):
    def process_request(self, request):
        ip = request.META.get('HTTP_X_FORWARDED_FOR')
        if ip:
            ip = ip.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        if ip in settings.EXCLUDE_AUTH_IP:
            request._dont_enforce_csrf_checks = True
            User = get_user_model()
            try:
                sysadmin = User.objects.get(username='sysadmin')
                request.user = sysadmin
            except User.DoesNotExist:
                request.user = AnonymousUser()