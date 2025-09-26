from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import *
from .views import UsersListView

router = DefaultRouter()
router.register(r'adapters', AdapterViewSet)
router.register(r'projects', ProjectViewSet)
router.register(r'project-versions', ProjectVersionViewSet)
router.register(r'devices', DeviceViewSet)
router.register(r'companies', DeviceCompanyViewSet)
router.register(r'user-manuals', UserManualViewSet)
router.register(r'data-names', DataNameViewSet)
router.register(r'control-values', ControlValueViewSet)
router.register(r'control-value-histories', ControlValueHistoryViewSet)
router.register(r'variables', VariableViewSet)
router.register(r'calc-variables', CalcVariableViewSet)
router.register(r'calc-groups', CalcGroupViewSet)
router.register(r'control-variables', ControlVariableViewSet)
router.register(r'control-logics', ControlLogicViewSet)
router.register(r'control-groups', ControlGroupViewSet)
router.register(r'location-groups', LocationGroupViewSet)
router.register(r'location-codes', LocationCodeViewSet)
router.register(r'modules', ModuleViewSet)
router.register(r'device-instances', DeviceInstanceViewSet)

urlpatterns = router.urls

urlpatterns += [
    path('user-preferences/<str:username>/', UserPreferencesView.as_view()),
    path('user-id-to-username/<int:user_id>/', UserIdToUsernameView.as_view()),
    path('users-admin/', UsersAdminListView.as_view()),
    path('projects/<int:project_id>/restore/<str:version>/', ProjectVersionRestoreView.as_view(), name='project-restore-version'),
    path('users-debug/', UsersListView.as_view()),
]