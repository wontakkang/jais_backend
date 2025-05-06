from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'projects', ProjectViewSet)
router.register(r'project-versions', ProjectVersionViewSet)
router.register(r'memory-groups', MemoryGroupViewSet)
router.register(r'variables', VariableViewSet)

urlpatterns = router.urls

urlpatterns += [
    path('user-preferences/<str:username>/', UserPreferencesView.as_view()),
    path('projects/<int:project_id>/restore/<str:version>/', ProjectVersionRestoreView.as_view(), name='project-restore-version'),
]