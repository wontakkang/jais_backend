from django.db import models

class BaseTimeSeries(models.Model):
    """해상도별 시계열 데이터의 공통 필드 정의(추상 클래스)."""
    timestamp = models.DateTimeField(db_index=True)
    client_id = models.PositiveIntegerField(db_index=True, help_text="클라이언트를 찾기 위한 id 값", verbose_name="클라이언트 ID")
    group_id = models.PositiveIntegerField(db_index=True, help_text="메모리그룹을 찾기 위한 id 값", verbose_name="메모리그룹 ID")
    var_id = models.PositiveIntegerField(db_index=True, help_text="변수를 찾기 위한 id 값", verbose_name="변수 ID")
    # 클라이언트, 메모리그룹, 디바이스를 찾기위한 id 값

    # 원시값(필요시 사용)
    value = models.FloatField(null=True, blank=True)
    # 새 필드: 값의 자료형을 저장 (예: int, float, bool, str)
    value_type = models.CharField(max_length=20, null=True, blank=True, help_text="값 자료형(int,float,bool,str 등)")

    # 집계 필드(예: 2분 치의 min/max/avg 등)
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    avg_value = models.FloatField(null=True, blank=True)
    sum_value = models.FloatField(null=True, blank=True)
    count = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-timestamp']


class TwoMinuteData(BaseTimeSeries):
    """2분 해상도 데이터 테이블"""

    class Meta:
        db_table = 'data_2min'
        verbose_name = '2분 데이터'
        verbose_name_plural = '2분 데이터'
        unique_together = ('timestamp', 'var_id')
        indexes = [models.Index(fields=['timestamp', 'var_id'])]


class TenMinuteData(BaseTimeSeries):
    """10분 해상도 데이터 테이블"""

    class Meta:
        db_table = 'data_10min'
        verbose_name = '10분 데이터'
        verbose_name_plural = '10분 데이터'
        unique_together = ('timestamp', 'var_id')
        indexes = [models.Index(fields=['timestamp', 'var_id'])]


class HourlyData(BaseTimeSeries):
    """1시간 해상도 데이터 테이블"""

    class Meta:
        db_table = 'data_1hour'
        verbose_name = '1시간 데이터'
        verbose_name_plural = '1시간 데이터'
        unique_together = ('timestamp', 'var_id')
        indexes = [models.Index(fields=['timestamp', 'var_id'])]


class DailyData(BaseTimeSeries):
    """하루(일간) 해상도 데이터 테이블"""

    class Meta:
        db_table = 'data_daily'
        verbose_name = '일별 데이터'
        verbose_name_plural = '일별 데이터'
        unique_together = ('timestamp', 'var_id')
        indexes = [models.Index(fields=['timestamp', 'var_id'])]

