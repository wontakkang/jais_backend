from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings
import os, time

class Command(BaseCommand):
    help = 'Migrate Adapter data from backup db.sqlite3.bak (LSISsocket_adapter) to corecode_adapter, and restore SensorNodeConfig.adapter FKs.'

    def add_arguments(self, parser):
        parser.add_argument('--backup', type=str, default='db.sqlite3.bak', help='Backup sqlite filename relative to BASE_DIR')

    def _safe_detach(self, alias='bak', retries=5, delay=0.2):
        last_err = None
        for _ in range(retries):
            try:
                with connection.cursor() as c2:
                    c2.execute(f"DETACH DATABASE {alias};")
                return True
            except Exception as e:
                last_err = e
                time.sleep(delay)
        if last_err:
            raise last_err
        return True

    def handle(self, *args, **options):
        base_dir = getattr(settings, 'BASE_DIR', os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) )
        backup_file = options['backup']
        backup_path = backup_file if os.path.isabs(backup_file) else os.path.join(base_dir, backup_file)
        if not os.path.exists(backup_path):
            self.stdout.write(self.style.ERROR(f'Backup file not found: {backup_path}'))
            return

        backup_path_sql = backup_path.replace("'", "''")

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA busy_timeout=5000;")
            cursor.execute("PRAGMA foreign_keys=OFF;")
            cursor.execute(f"ATTACH DATABASE '{backup_path_sql}' AS bak;")

            # Copy adapters
            self.stdout.write('Copying adapters from backup...')
            cursor.execute(
                """
                INSERT INTO corecode_adapter (id, name, description, protocol, config, created_at, updated_at, is_deleted)
                SELECT b.id, b.name, b.description, b.protocol, b.config, b.created_at, b.updated_at, b.is_deleted
                FROM bak.LSISsocket_adapter b
                WHERE b.id NOT IN (SELECT id FROM corecode_adapter);
                """
            )
            cursor.execute("SELECT COUNT(1) FROM corecode_adapter;")
            total_adapters = cursor.fetchone()[0]

            # Restore SensorNodeConfig.adapter FKs
            self.stdout.write('Restoring SensorNodeConfig.adapter FKs...')
            cursor.execute(
                """
                UPDATE LSISsocket_sensornodeconfig AS cur
                SET adapter_id = (
                    SELECT b.adapter_id FROM bak.LSISsocket_sensornodeconfig b WHERE b.id = cur.id
                )
                WHERE cur.adapter_id IS NULL
                AND EXISTS (SELECT 1 FROM bak.LSISsocket_sensornodeconfig b WHERE b.id = cur.id AND b.adapter_id IS NOT NULL);
                """
            )
            cursor.execute("SELECT COUNT(1) FROM LSISsocket_sensornodeconfig WHERE adapter_id IS NOT NULL;")
            sensornode_fk_count = cursor.fetchone()[0]

        # 트랜잭션이 자동 커밋된 후 DETACH 시도
        try:
            self._safe_detach('bak', retries=10, delay=0.3)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA foreign_keys=ON;")

        self.stdout.write(self.style.SUCCESS(f'Adapter migration completed. corecode_adapter total={total_adapters}, SensorNodeConfig with adapter={sensornode_fk_count}'))
