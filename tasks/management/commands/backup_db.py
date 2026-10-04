import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Создать согласованную резервную копию SQLite перед миграцией.'
    requires_system_checks = []

    def handle(self, *args, **options):
        source = Path(settings.DATABASES['default']['NAME']).resolve()
        if not source.exists():
            self.stdout.write('База ещё не создана: резервная копия не нужна.')
            return
        folder = settings.BASE_DIR / 'backups'
        folder.mkdir(exist_ok=True)
        destination = folder / ('db-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
        try:
            with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as db:
                with closing(sqlite3.connect(destination)) as backup:
                    db.backup(backup)
        except sqlite3.Error as error:
            raise CommandError('Не удалось создать резервную копию SQLite.') from error
        self.stdout.write(str(destination))
