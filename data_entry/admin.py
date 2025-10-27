from django.contrib import admin
from . import models


@admin.register(models.TwoMinuteData)
class TwoMinuteDataAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'var_id', 'value', 'min_value', 'max_value', 'avg_value', 'count')
    search_fields = ('var_id',)
    list_filter = ('var_id',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(models.TenMinuteData)
class TenMinuteDataAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'var_id', 'value', 'min_value', 'max_value', 'avg_value', 'count')
    search_fields = ('var_id',)
    list_filter = ('var_id',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(models.HourlyData)
class HourlyDataAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'var_id', 'value', 'min_value', 'max_value', 'avg_value', 'count')
    search_fields = ('var_id',)
    list_filter = ('var_id',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(models.DailyData)
class DailyDataAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'var_id', 'value', 'min_value', 'max_value', 'avg_value', 'count')
    search_fields = ('var_id',)
    list_filter = ('var_id',)
    readonly_fields = ('created_at', 'updated_at')
