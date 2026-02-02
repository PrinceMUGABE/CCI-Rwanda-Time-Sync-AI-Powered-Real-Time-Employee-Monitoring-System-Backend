# Create file: yourapp/management/commands/check_timezone.py
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from django.db import connection
import pytz
from datetime import datetime

class Command(BaseCommand):
    help = 'Check timezone configuration'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== TIMEZONE CONFIGURATION ===\n'))
        
        # System timezone
        try:
            import tzlocal
            system_tz = tzlocal.get_localzone_name()
            self.stdout.write(f"System Timezone: {system_tz}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"System detection error: {e}"))
        
        # Django settings
        self.stdout.write(f"Django TIME_ZONE setting: {settings.TIME_ZONE}")
        self.stdout.write(f"Django USE_TZ setting: {settings.USE_TZ}")
        
        # Current timezone
        current_tz = timezone.get_current_timezone()
        self.stdout.write(f"Active Django timezone: {current_tz}")
        
        # Current time
        now = timezone.now()
        self.stdout.write(f"Current Django time: {now}")
        
        # UTC offset
        tz = pytz.timezone(settings.TIME_ZONE)
        offset = tz.utcoffset(datetime.now())
        offset_hours = int(offset.total_seconds() / 3600)
        self.stdout.write(f"UTC Offset: {offset_hours:+d} hours")
        
        # MySQL timezone
        self.stdout.write(self.style.SUCCESS('\n=== MYSQL CONFIGURATION ===\n'))
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    @@session.time_zone as session_tz,
                    @@global.time_zone as global_tz,
                    @@system_time_zone as system_tz,
                    NOW() as mysql_now,
                    UTC_TIMESTAMP() as mysql_utc
            """)
            result = cursor.fetchone()
            self.stdout.write(f"MySQL Session TZ: {result[0]}")
            self.stdout.write(f"MySQL Global TZ: {result[1]}")
            self.stdout.write(f"MySQL System TZ: {result[2]}")
            self.stdout.write(f"MySQL NOW(): {result[3]}")
            self.stdout.write(f"MySQL UTC_TIMESTAMP(): {result[4]}")
        
        self.stdout.write(self.style.SUCCESS('\n=== STATUS ===\n'))
        if str(current_tz) == settings.TIME_ZONE:
            self.stdout.write(self.style.SUCCESS('✓ Django timezone matches settings'))
        else:
            self.stdout.write(self.style.WARNING('⚠ Django timezone mismatch'))
        
        self.stdout.write(self.style.SUCCESS('✓ Configuration check complete\n'))