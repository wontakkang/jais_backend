import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class ComplexPasswordValidator:
    """비밀번호 복잡성 검증기: 길이, 대문자/소문자/숫자/특수문자 포함 여부를 검사합니다."""
    def __init__(self, min_length=8, require_upper=True, require_lower=True, require_digit=True, require_special=True):
        self.min_length = int(min_length)
        self.require_upper = str(require_upper).lower() in ('true', '1', 'yes') if isinstance(require_upper, str) else bool(require_upper)
        self.require_lower = str(require_lower).lower() in ('true', '1', 'yes') if isinstance(require_lower, str) else bool(require_lower)
        self.require_digit = str(require_digit).lower() in ('true', '1', 'yes') if isinstance(require_digit, str) else bool(require_digit)
        self.require_special = str(require_special).lower() in ('true', '1', 'yes') if isinstance(require_special, str) else bool(require_special)
        self.special_regex = re.compile(r'[!@#$%^&*(),.?":{}|<>~`\[\]\-_=+/;\\\']')

    def validate(self, password, user=None):
        errors = []
        if password is None:
            raise ValidationError(_('비밀번호가 없습니다.'))
        if len(password) < self.min_length:
            errors.append(ValidationError(
                _('비밀번호는 최소 %(min_length)d자 이상이어야 합니다.'),
                params={'min_length': self.min_length}
            ))
        if self.require_upper and not re.search(r'[A-Z]', password):
            errors.append(ValidationError(_('대문자를 하나 이상 포함해야 합니다.')))
        if self.require_lower and not re.search(r'[a-z]', password):
            errors.append(ValidationError(_('소문자를 하나 이상 포함해야 합니다.')))
        if self.require_digit and not re.search(r'\d', password):
            errors.append(ValidationError(_('숫자를 하나 이상 포함해야 합니다.')))
        if self.require_special and not self.special_regex.search(password):
            errors.append(ValidationError(_('특수문자(예: !@#$%)를 하나 이상 포함해야 합니다.')))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        parts = [f"최소 {self.min_length}자"]
        if self.require_upper:
            parts.append('대문자 포함')
        if self.require_lower:
            parts.append('소문자 포함')
        if self.require_digit:
            parts.append('숫자 포함')
        if self.require_special:
            parts.append('특수문자 포함')
        return _('비밀번호는 ') + ', '.join(parts) + _(' 해야 합니다.')
