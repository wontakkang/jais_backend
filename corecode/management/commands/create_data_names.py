from django.core.management.base import BaseCommand
from corecode.models import DataName

DEFAULTS = [
    {"name": "ssc_brix", "ctype": "numeric", "dtype": "float", "unit": "Brix", "attributes": "reference", "method_description": "당도(Brix)", "method_result_type": "float"},
    {"name": "titratable_acidity_percent", "ctype": "numeric", "dtype": "float", "unit": "%", "attributes": "reference", "method_description": "적정산도(%)", "method_result_type": "float"},
    {"name": "sugar_acid_ratio", "ctype": "numeric", "dtype": "float", "unit": "ratio", "attributes": "reference", "method_description": "당/산비(Brix/TA)", "method_result_type": "float"},
    {"name": "fruit_diameter_mm", "ctype": "numeric", "dtype": "float", "unit": "mm", "attributes": "reference", "method_description": "과실 직경(mm)", "method_result_type": "float"},
    {"name": "fruit_weight_g", "ctype": "numeric", "dtype": "float", "unit": "g", "attributes": "reference", "method_description": "과실 무게(g)", "method_result_type": "float"},
    {"name": "peel_thickness_mm", "ctype": "numeric", "dtype": "float", "unit": "mm", "attributes": "reference", "method_description": "과피 두께(mm)", "method_result_type": "float"},
    {"name": "juice_yield_percent", "ctype": "numeric", "dtype": "float", "unit": "%", "attributes": "reference", "method_description": "착즙율(%)", "method_result_type": "float"},
    {"name": "LAI", "ctype": "numeric", "dtype": "float", "unit": "", "attributes": "reference", "method_description": "잎면적지수", "method_result_type": "float"},
    {"name": "defect_rate_percent", "ctype": "numeric", "dtype": "float", "unit": "%", "attributes": "reference", "method_description": "결함율(%)", "method_result_type": "float"},
    {"name": "firmness_N", "ctype": "numeric", "dtype": "float", "unit": "N", "attributes": "reference", "method_description": "경도(N)", "method_result_type": "float"},
]

class Command(BaseCommand):
    help = 'Create or update DataName entries for 온주밀감 측정요소들.'

    def add_arguments(self, parser):
        parser.add_argument('--noinput', action='store_true', help='변경 없이 어떤 항목이 생성/갱신될지 출력만 함')

    def handle(self, *args, **options):
        dry = options.get('noinput', False)
        created = []
        updated = []
        for item in DEFAULTS:
            name = item['name']
            obj, exists = None, False
            try:
                obj = DataName.objects.filter(name=name).first()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"DB 접근 오류: {e}"))
                return
            if obj:
                exists = True
                # 비교 후 필요시 갱신
                changed = False
                for k, v in item.items():
                    if hasattr(obj, k) and getattr(obj, k) != v:
                        setattr(obj, k, v)
                        changed = True
                if changed and not dry:
                    obj.save()
                    updated.append(name)
                elif changed and dry:
                    updated.append(name)
            else:
                if not dry:
                    DataName.objects.create(**item)
                    created.append(name)
                else:
                    created.append(name)
        self.stdout.write(self.style.SUCCESS(f"To create: {len(created)}, To update: {len(updated)}"))
        if created:
            self.stdout.write('Created: ' + ', '.join(created))
        if updated:
            self.stdout.write('Updated: ' + ', '.join(updated))
