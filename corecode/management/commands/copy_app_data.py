from django.core.management.base import BaseCommand, CommandParser
from django.apps import apps
from django.db import connections, router, transaction

class Command(BaseCommand):
    help = 'Copy data for given apps from source DB to target DB (data-only).'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('apps', nargs='+', help='App labels to copy (e.g., corecode agriseed LSISsocket MCUnode)')
        parser.add_argument('--source', default='default', help='Source DB alias (default)')
        parser.add_argument('--target', default='target', help='Target DB alias (target)')
        parser.add_argument('--chunk', type=int, default=1000, help='Bulk chunk size')

    def handle(self, *args, **opts):
        source = opts['source']
        target = opts['target']
        chunk = opts['chunk']
        conn_tgt = connections[target]
        vendor = conn_tgt.vendor
        cursor = conn_tgt.cursor()
        try:
            if vendor == 'mysql':
                cursor.execute('SET FOREIGN_KEY_CHECKS=0')
            for app_label in opts['apps']:
                app_config = apps.get_app_config(app_label)
                # 먼저 일반 모델(자동생성 M2M 제외)
                normal_models = [m for m in app_config.get_models(include_auto_created=False)]
                # 그 다음 자동 생성된 M2M through 모델들
                m2m_models = [m for m in app_config.get_models(include_auto_created=True) if getattr(m._meta, 'auto_created', False)]

                for Model in normal_models:
                    qs = Model._default_manager.using(source).all().order_by('pk')
                    total = qs.count()
                    copied = 0
                    self.stdout.write(f'[{app_label}] {Model.__name__}: {total} rows')
                    start = 0
                    while start < total:
                        batch = list(qs[start:start+chunk])
                        # detach state
                        for obj in batch:
                            obj._state.adding = True
                            obj._state.db = target
                        Model._default_manager.using(target).bulk_create(batch, ignore_conflicts=True)
                        copied += len(batch)
                        start += chunk
                    self.stdout.write(self.style.SUCCESS(f'[{app_label}] {Model.__name__}: copied {copied}'))

                for Through in m2m_models:
                    qs = Through._default_manager.using(source).all()
                    total = qs.count()
                    copied = 0
                    self.stdout.write(f'[{app_label}] M2M {Through.__name__}: {total} rows')
                    start = 0
                    while start < total:
                        batch = list(qs[start:start+chunk])
                        for obj in batch:
                            obj._state.adding = True
                            obj._state.db = target
                        Through._default_manager.using(target).bulk_create(batch, ignore_conflicts=True)
                        copied += len(batch)
                        start += chunk
                    self.stdout.write(self.style.SUCCESS(f'[{app_label}] M2M {Through.__name__}: copied {copied}'))
        finally:
            if vendor == 'mysql':
                cursor.execute('SET FOREIGN_KEY_CHECKS=1')
            conn_tgt.commit()
        self.stdout.write(self.style.SUCCESS('Done'))
