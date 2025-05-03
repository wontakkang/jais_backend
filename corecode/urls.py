from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet, ProjectVersionViewSet, MemoryGroupViewSet, VariableViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet)
router.register(r'project-versions', ProjectVersionViewSet)
router.register(r'memory-groups', MemoryGroupViewSet)
router.register(r'variables', VariableViewSet)

urlpatterns = router.urls