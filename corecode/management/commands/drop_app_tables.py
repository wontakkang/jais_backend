from django.core.management.base import BaseCommand, CommandParser
from django.db import connections

APP_PREFIXES = {
    'agriseed': 'agriseed_',
    'corecode': 'corecode_',
    'LSISsocket': 'LSISsocket_',
    'MCUnode': 'MCUnode_',
}

class Command(BaseCommand):
    help = 'Drop all tables for given apps in the specified database and clear their django_migrations rows.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('apps', nargs='+', help='App labels to drop (e.g., agriseed corecode LSISsocket MCUnode)')
        parser.add_argument('--database', default='default', help='Database alias (default: default)')

    def handle(self, *args, **options):
        alias = options['database']
        apps = options['apps']
        prefixes = [APP_PREFIXES[a] for a in apps if a in APP_PREFIXES]
        if not prefixes:
            self.stdout.write(self.style.WARNING('No valid app prefixes resolved. Nothing to do.'))
            return

        conn = connections[alias]
        vendor = conn.vendor  # 'mysql', 'sqlite', 'postgresql'
        with conn.cursor() as c:
            if vendor == 'mysql':
                c.execute('SET FOREIGN_KEY_CHECKS=0')
            # introspect and drop tables
            tables = conn.introspection.table_names()
            target_tables = [t for t in tables if any(t.startswith(p) for p in prefixes)]
            for t in target_tables:
                c.execute(f"DROP TABLE IF EXISTS `{t}`")
            # clear migration rows
            in_clause = ','.join(['%s'] * len(apps))
            c.execute(f"DELETE FROM django_migrations WHERE app IN ({in_clause})", apps)
            if vendor == 'mysql':
                c.execute('SET FOREIGN_KEY_CHECKS=1')
        conn.commit()
        self.stdout.write(self.style.SUCCESS(f'Dropped {len(target_tables)} tables and cleared migrations for apps: {", ".join(apps)}'))
