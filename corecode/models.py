from django.contrib.auth.models import AbstractUser
from django.db import models

from utils.calculation import __all__ as calculation_methods
from utils.calculation import all_dict
from utils.control import __all__ as control_methods
from utils.control import all_dict as control_methods_dict

class User(AbstractUser):
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='corecode_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='corecode_user_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )
    profile_image = models.ImageField(
        upload_to='profile_images/',
        null=True,
        blank=True,
        help_text='사용자 프로필 이미지',
    )

class UserPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preference')
    preferences = models.JSONField(default=dict, blank=True, help_text="개인화 설정(예: 테마, 알림 등)")

    def __str__(self):
        return f"{self.user.username}의 환경설정"


#데이터 명칭, 단위
class DataName(models.Model):
    name = models.CharField(max_length=100, unique=True)
    ctype = models.CharField(max_length=20, blank=True)
    dtype = models.CharField(max_length=10, blank=True)
    unit = models.CharField(max_length=20, blank=True)
    DATA_TYPE_CHOICES = [
        ('status', 'Status'),
        ('upper', 'Upper'),
        ('lower', 'Lower'),
        ('reference', 'Reference'),
        ('difference', 'Difference'),
        ('calculation', 'Calculation'),
        ('command', 'Command'),
    ]
    attributes = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES, null=True, blank=True)
    use_method = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        choices=[(method, method) for method in calculation_methods + control_methods]
    )
    method_description = models.CharField(max_length=200, null=True, blank=True)
    method_args_desc = models.JSONField(default=dict, null=True, blank=True, help_text="계산 메서드 인자 설명")
    method_result = models.JSONField(default=dict, null=True, blank=True, help_text="계산 메서드 인자 설명")
    method_args_type = models.JSONField(default=dict, null=True, blank=True, help_text="계산 메서드 인자 타입")
    method_result_type = models.CharField(max_length=100, null=True, blank=True, help_text="계산 메서드 반환 타입")
    icon = models.CharField(max_length=100, blank=True, null=True, help_text="아이콘 클래스 (문자열)")
    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # use_method가 지정되어 있으면 함수 설명, 인자, 인자설명, 반환 형식 자동 저장
        if self.use_method:
            import inspect
            import re
            from utils.calculation import all_dict as calculation_all_dict
            from utils.control import all_dict as control_all_dict
            
            func = calculation_all_dict.get(self.use_method) or control_all_dict.get(self.use_method)
            if func:
                doc = inspect.getdoc(func)
                return_desc = None
                return_type = None
                if doc:
                    # return 설명 추출
                    return_match = re.search(r"\n:return: ([^\n]+)", doc)
                    if return_match:
                        return_desc = return_match.group(1).strip()
                    # 반환 타입 추출 (예: :rtype: float)
                    rtype_match = re.search(r"\n:rtype: ([^\n]+)", doc)
                    if rtype_match:
                        return_type = rtype_match.group(1).strip()
                    doc = re.sub(r"\n:param [^:]+:.*?(?=\n|$)", "", doc)
                    doc = re.sub(r"\n:return:.*?(?=\n|$)", "", doc)
                    doc = re.sub(r"\n:rtype:.*?(?=\n|$)", "", doc)
                    doc = doc.strip()
                self.method_description = doc
                param_desc = {}
                param_type = {}
                if inspect.getdoc(func):
                    matches = re.findall(r":param (\w+): ([^\n]+)", inspect.getdoc(func))
                    for name, desc in matches:
                        param_desc[name] = desc
                    # 타입 힌트 추출
                    sig = inspect.signature(func)
                    for name, param in sig.parameters.items():
                        if param.annotation != inspect.Parameter.empty:
                            ann = param.annotation
                            # float, int는 number로 통일, list/str 등은 그대로
                            if hasattr(ann, '__name__'):
                                if ann.__name__ in ('float', 'int'):
                                    param_type[name] = 'number'
                                else:
                                    param_type[name] = ann.__name__
                            else:
                                ann_str = str(ann)
                                if ann_str in ("<class 'float'>", "<class 'int'>"):
                                    param_type[name] = 'number'
                                else:
                                    param_type[name] = ann_str
                self.method_args_desc = param_desc  # key-value JSON 저장
                self.method_args_type = param_type  # key-type JSON 저장 (필드 필요)
                self.method_result = return_desc
                # 반환 타입은 예외 없이 원본 그대로 저장
                self.method_result_type = return_type
            else:
                self.method_description = None
                self.method_args_desc = {}
                self.method_args_type = {}
                self.method_result = None
                self.method_result_type = None
        else:
            self.method_description = None
            self.method_args_desc = {}
            self.method_args_type = {}
            self.method_result = None
            self.method_result_type = None
        super().save(*args, **kwargs)
    
class UserManual(models.Model):
    """
    사용자 취급 메뉴얼 정보를 관리하는 모델
    """
    title = models.CharField(max_length=200, help_text="메뉴얼 제목")
    file = models.FileField(upload_to='user_manuals/', help_text="사용자 취급 메뉴얼 파일")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    
class DeviceCompany(models.Model):
    """
    장비 제조사 정보를 관리하는 모델
    """
    name = models.CharField(max_length=100, unique=True)
    address = models.TextField(blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)

    def __str__(self):
        return self.name
    
class Device(models.Model):
    name = models.CharField(max_length=100, unique=True)
    DEVICE_TYPE_CHOICES = [
        ('sensor', 'Sensor'),
        ('actuator', 'Actuator'),
        ('controller', 'Controller'),
        ('other', 'Other'),
    ]
    device_code = models.CharField(max_length=20, null=True, blank=True)
    device_name_korean = models.CharField(max_length=200, null=True, blank=True, help_text="단체표준 장비명(국문)")
    device_name_english = models.CharField(max_length=200, null=True, blank=True, help_text="Standardized device name (English)")
    device_type = models.CharField(max_length=50, choices=DEVICE_TYPE_CHOICES)
    icon = models.ImageField(upload_to='device_icons/', null=True, blank=True)
    alert_icon = models.ImageField(upload_to='device_icons/alert/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    manufacturer = models.ForeignKey('DeviceCompany', on_delete=models.CASCADE, null=True, blank=True, related_name='devices')
    
    CONNECTOR_TYPE_CHOICES = [
        ('LSIS-socket', 'LSIS-socket'),
    ]
    connector = models.CharField(max_length=50, null=True, blank=True, choices=CONNECTOR_TYPE_CHOICES)
    catalog = models.FileField(upload_to='device_catalogs/', null=True, blank=True, help_text="장비 카탈로그 파일")
    user_manuals = models.ManyToManyField('UserManual', blank=True, related_name='devices', help_text="사용자 취급 메뉴얼 파일들")

    def __str__(self):
        return self.name


class ControlLogic(models.Model):
    """
    제어 로직 정의 (공통 사용)
    """
    name = models.CharField(max_length=100, blank=True, null=True, help_text="제어 로직 이름")
    use_method = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        choices=[(method, method) for method in control_methods]
    )
    method_description = models.CharField(max_length=200, null=True, blank=True)
    method_args_desc = models.JSONField(default=dict, null=True, blank=True, help_text="메서드 인자 설명")
    method_result = models.JSONField(default=dict, null=True, blank=True, help_text="메서드 결과 설명")
    method_args_type = models.JSONField(default=dict, null=True, blank=True, help_text="메서드 인자 타입")
    method_result_type = models.CharField(max_length=100, null=True, blank=True, help_text="메서드 반환 타입")
    
    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.use_method:
            import inspect
            import re
            from utils.control import all_dict as control_all_dict
            
            func = control_all_dict.get(self.use_method)
            if func:
                doc = inspect.getdoc(func)
                return_desc = None
                return_type = None
                if doc:
                    return_match = re.search(r"\n:return: ([^\n]+)", doc)
                    if return_match:
                        return_desc = return_match.group(1).strip()
                    rtype_match = re.search(r"\n:rtype: ([^\n]+)", doc)
                    if rtype_match:
                        return_type = rtype_match.group(1).strip()
                    doc_cleaned = re.sub(r"\n:param [^:]+:.*?(?=\n|$)", "", doc)
                    doc_cleaned = re.sub(r"\n:return:.*?(?=\n|$)", "", doc_cleaned)
                    doc_cleaned = re.sub(r"\n:rtype:.*?(?=\n|$)", "", doc_cleaned)
                    self.method_description = doc_cleaned.strip()
                else:
                    self.method_description = None
                
                param_desc = {}
                param_type = {}
                if inspect.getdoc(func): # inspect.getdoc(func) can be None
                    sig = inspect.signature(func)
                    doc_str = inspect.getdoc(func)
                    matches = re.findall(r":param (\w+): ([^\n]+)", doc_str)
                    for p_name, desc in matches:
                        param_desc[p_name] = desc
                    for p_name, param in sig.parameters.items():
                        if param.annotation != inspect.Parameter.empty:
                            ann = param.annotation
                            if hasattr(ann, '__name__'):
                                if ann.__name__ in ('float', 'int'):
                                    param_type[p_name] = 'number'
                                else:
                                    param_type[p_name] = ann.__name__
                            else:
                                ann_str = str(ann)
                                if ann_str in ("<class 'float'>", "<class 'int'>"):
                                    param_type[p_name] = 'number'
                                else:
                                    param_type[p_name] = ann_str
                self.method_args_desc = param_desc
                self.method_args_type = param_type
                self.method_result = return_desc
                self.method_result_type = return_type
            else:
                self.method_description = None
                self.method_args_desc = {}
                self.method_args_type = {}
                self.method_result = None
                self.method_result_type = None
        else:
            self.method_description = None
            self.method_args_desc = {}
            self.method_args_type = {}
            self.method_result = None
            self.method_result_type = None
        super().save(*args, **kwargs)
    
# 어댑터 모델을 corecode로 이동
class ActiveAdapterManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class Adapter(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="어댑터 이름")
    description = models.TextField(null=True, blank=True, help_text="설명")
    protocol = models.CharField(max_length=50, help_text="프로토콜 종류 (예: TCP, MQTT, HTTP 등)")
    config = models.JSONField(null=True, blank=True, help_text="어댑터별 추가 설정값")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, help_text="삭제 여부")

    objects = ActiveAdapterManager()  # 삭제되지 않은 것만 조회
    all_objects = models.Manager()    # 전체(삭제 포함) 조회

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.save()

    def restore(self):
        self.is_deleted = False
        self.save()

    def __str__(self):
        return self.name



