# Generated by Django 5.2 on 2025-04-26 06:04

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ControlRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('icon', models.CharField(max_length=100)),
                ('icon_bg', models.CharField(max_length=100)),
                ('conditions', models.JSONField()),
                ('actions', models.JSONField()),
                ('last_executed', models.DateTimeField()),
                ('active', models.BooleanField()),
            ],
        ),
        migrations.CreateModel(
            name='Device',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('device_id', models.CharField(max_length=50, unique=True)),
                ('icon', models.CharField(max_length=100)),
                ('battery', models.IntegerField()),
                ('firmware', models.CharField(max_length=50)),
                ('last_data', models.CharField(max_length=50)),
                ('location', models.CharField(max_length=100)),
                ('installed_at', models.DateField()),
                ('status', models.CharField(max_length=50)),
                ('type', models.CharField(max_length=50)),
                ('info_link', models.URLField()),
            ],
        ),
        migrations.CreateModel(
            name='Facility',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='Unknown Facility', help_text='시설 이름', max_length=100)),
                ('type', models.CharField(default='vinyl', help_text='시설 유형 (예: vinyl, glass 등)', max_length=50)),
                ('location', models.CharField(default='Unknown Location', help_text='시설 위치', max_length=200)),
                ('area', models.FloatField(default=100.0, help_text='시설 면적 (기본값: 100 제곱미터)')),
                ('zone_count', models.IntegerField(default=1, help_text='구역 수 (기본값: 1)')),
                ('manager', models.CharField(default='Unknown Manager', help_text='시설 관리자', max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name='Issue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(max_length=50)),
                ('title', models.CharField(max_length=200)),
                ('time', models.DateTimeField()),
                ('details', models.JSONField()),
                ('button_label', models.CharField(max_length=100)),
                ('icon', models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name='ResolvedIssue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('title', models.CharField(max_length=200)),
                ('action', models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='Schedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('icon', models.CharField(max_length=100)),
                ('title', models.CharField(max_length=200)),
                ('schedule', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('enabled', models.BooleanField()),
            ],
        ),
        migrations.CreateModel(
            name='ControlHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('time', models.DateTimeField()),
                ('action', models.CharField(max_length=200)),
                ('trigger', models.CharField(max_length=200)),
                ('status', models.CharField(max_length=50)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='control_histories', to='agriseed.device')),
            ],
        ),
        migrations.CreateModel(
            name='Activity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('time', models.DateTimeField()),
                ('event', models.CharField(max_length=200)),
                ('status', models.CharField(max_length=50)),
                ('location', models.CharField(max_length=100)),
                ('icon', models.CharField(max_length=100)),
                ('icon_class', models.CharField(max_length=100)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activities', to='agriseed.device')),
            ],
        ),
        migrations.CreateModel(
            name='Zone',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='Default Zone', help_text='구역 이름', max_length=100)),
                ('type', models.CharField(default='온실', help_text='구역 유형 (예: 온실, 저장고 등)', max_length=50)),
                ('area', models.FloatField(default=50.0, help_text='구역 면적 (기본값: 50 제곱미터)')),
                ('facility', models.ForeignKey(help_text='소속된 시설', on_delete=django.db.models.deletion.CASCADE, related_name='zones', to='agriseed.facility')),
            ],
        ),
        migrations.CreateModel(
            name='SensorData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('temperature', models.FloatField(default=24.5, help_text='온도 (기본값: 24.5°C)')),
                ('humidity', models.FloatField(default=65.0, help_text='습도 (기본값: 65%)')),
                ('light', models.FloatField(default=350.0, help_text='조도 (기본값: 350 lux)')),
                ('soil_moisture', models.FloatField(default=42.0, help_text='토양 수분 (기본값: 42%)')),
                ('timestamp', models.DateTimeField(auto_now_add=True, help_text='데이터 생성 시간')),
                ('zone', models.ForeignKey(help_text='소속된 구역', on_delete=django.db.models.deletion.CASCADE, related_name='sensor_data', to='agriseed.zone')),
            ],
        ),
        migrations.CreateModel(
            name='FacilityHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('temperature', models.JSONField(default=list, help_text='온도 기록')),
                ('humidity', models.JSONField(default=list, help_text='습도 기록')),
                ('light', models.JSONField(default=list, help_text='조도 기록')),
                ('soil_moisture', models.JSONField(default=list, help_text='토양 수분 기록')),
                ('zone', models.ForeignKey(help_text='소속된 구역', on_delete=django.db.models.deletion.CASCADE, related_name='history', to='agriseed.zone')),
            ],
        ),
        migrations.CreateModel(
            name='ControlSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fan_is_on', models.BooleanField(default=False, help_text='팬 작동 여부 (기본값: 꺼짐)')),
                ('fan_speed', models.IntegerField(default=50, help_text='팬 속도 (기본값: 50%)')),
                ('water_is_on', models.BooleanField(default=False, help_text='물 공급 여부 (기본값: 꺼짐)')),
                ('water_flow', models.FloatField(default=2.5, help_text='물 흐름 속도 (기본값: 2.5 L/min)')),
                ('vent_open', models.IntegerField(default=50, help_text='환기구 개방 정도 (기본값: 50%)')),
                ('light_is_on', models.BooleanField(default=False, help_text='조명 작동 여부 (기본값: 꺼짐)')),
                ('light_intensity', models.IntegerField(default=50, help_text='조명 강도 (기본값: 50%)')),
                ('auto_mode', models.BooleanField(default=True, help_text='자동 모드 여부 (기본값: 켜짐)')),
                ('schedule_start', models.TimeField(default='06:00', help_text='스케줄 시작 시간 (기본값: 06:00)')),
                ('schedule_end', models.TimeField(default='18:00', help_text='스케줄 종료 시간 (기본값: 18:00)')),
                ('zone', models.ForeignKey(help_text='소속된 구역', on_delete=django.db.models.deletion.CASCADE, related_name='control_settings', to='agriseed.zone')),
            ],
        ),
    ]
