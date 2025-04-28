from rest_framework import viewsets
from .models import *
from .serializers import *

class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer

class ActivityViewSet(viewsets.ModelViewSet):
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer

class ControlHistoryViewSet(viewsets.ModelViewSet):
    queryset = ControlHistory.objects.all()
    serializer_class = ControlHistorySerializer

class ControlRoleViewSet(viewsets.ModelViewSet):
    queryset = ControlRole.objects.all()
    serializer_class = ControlRoleSerializer

class IssueViewSet(viewsets.ModelViewSet):
    queryset = Issue.objects.all()
    serializer_class = IssueSerializer

class ResolvedIssueViewSet(viewsets.ModelViewSet):
    queryset = ResolvedIssue.objects.all()
    serializer_class = ResolvedIssueSerializer

class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer

class FacilityViewSet(viewsets.ModelViewSet):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer

class ZoneViewSet(viewsets.ModelViewSet):
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer

class SensorDataViewSet(viewsets.ModelViewSet):
    queryset = SensorData.objects.all()
    serializer_class = SensorDataSerializer

class ControlSettingsViewSet(viewsets.ModelViewSet):
    queryset = ControlSettings.objects.all()
    serializer_class = ControlSettingsSerializer

class FacilityHistoryViewSet(viewsets.ModelViewSet):
    queryset = FacilityHistory.objects.all()
    serializer_class = FacilityHistorySerializer

class CropViewSet(viewsets.ModelViewSet):
    queryset = Crop.objects.all()
    serializer_class = CropSerializer

class VarietyViewSet(viewsets.ModelViewSet):
    queryset = Variety.objects.all()
    serializer_class = VarietySerializer

class VarietyImageViewSet(viewsets.ModelViewSet):
    queryset = VarietyImage.objects.all()
    serializer_class = VarietyImageSerializer

class VarietyGuideViewSet(viewsets.ModelViewSet):
    queryset = VarietyGuide.objects.all()
    serializer_class = VarietyGuideSerializer
