from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import *
from .views import UsersListView, logging_view

router = DefaultRouter()
router.register(r'adapters', AdapterViewSet)
router.register(r'devices', DeviceViewSet)
router.register(r'companies', DeviceCompanyViewSet)
router.register(r'user-manuals', UserManualViewSet)
router.register(r'data-names', DataNameViewSet)
router.register(r'control-logics', ControlLogicViewSet)

urlpatterns = router.urls

urlpatterns += [
    path('user-preferences/<str:username>/', UserPreferencesView.as_view()),
    path('user-id-to-username/<int:user_id>/', UserIdToUsernameView.as_view()),
    path('users-admin/', UsersAdminListView.as_view()),
    path('users-debug/', UsersListView.as_view()),
    path('logging/', logging_view),
    path('logging/tail/', LoggerTailView.as_view()),
]