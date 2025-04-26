from django.contrib import admin
from .models import Device, Activity, ControlHistory, ControlRole, Issue, ResolvedIssue, Schedule, Facility, Zone, SensorData, ControlSettings, FacilityHistory

admin.site.register(Device)
admin.site.register(Activity)
admin.site.register(ControlHistory)
admin.site.register(ControlRole)
admin.site.register(Issue)
admin.site.register(ResolvedIssue)
admin.site.register(Schedule)
admin.site.register(Facility)
admin.site.register(Zone)
admin.site.register(SensorData)
admin.site.register(ControlSettings)
admin.site.register(FacilityHistory)
