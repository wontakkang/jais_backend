from django.core.management.base import BaseCommand
from django.core.management import call_command
import os

class Command(BaseCommand):
    help = 'Load corecode fixtures from data.json into database'

    def handle(self, *args, **options):
        # Expect data.json at project root or in fixtures folder
        self.stdout.write('Loading data.json into database...')
        try:
            # If data.json in app fixtures, loaddata will find it
            call_command('loaddata', 'data.json')
            self.stdout.write(self.style.SUCCESS('Data loaded successfully.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error loading data.json: {e}'))
