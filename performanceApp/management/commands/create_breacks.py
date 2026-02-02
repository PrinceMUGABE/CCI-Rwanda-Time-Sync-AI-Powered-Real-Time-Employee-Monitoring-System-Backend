# performanceApp/management/commands/create_breaks.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from userApp.models import CustomUser
from performanceApp.services import BreakManagementService


class Command(BaseCommand):
    help = 'Create break logs for all users with assigned shifts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            help='Date in YYYY-MM-DD format (default: today)',
            type=str,
        )
        parser.add_argument(
            '--user',
            help='Specific user ID to create breaks for',
            type=int,
        )

    def handle(self, *args, **options):
        date_str = options.get('date')
        user_id = options.get('user')
        
        if date_str:
            date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date = timezone.now().date()
        
        self.stdout.write(f"Creating breaks for date: {date}")
        
        if user_id:
            # Create breaks for specific user
            try:
                user = CustomUser.objects.get(id=user_id)
                self.stdout.write(f"Creating breaks for user: {user.names} (ID: {user.id})")
                
                if not user.current_shift:
                    self.stdout.write(self.style.ERROR(f"User {user.names} has no assigned shift!"))
                    return
                
                breaks = BreakManagementService.create_breaks_for_user_shift(user, date)
                self.stdout.write(self.style.SUCCESS(f"Created {len(breaks)} breaks for {user.names}"))
                
                for br in breaks:
                    self.stdout.write(f"  - {br.break_template.name}: {br.scheduled_start.strftime('%H:%M')} to {br.scheduled_end.strftime('%H:%M')}")
                    
            except CustomUser.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"User with ID {user_id} not found"))
        else:
            # Create breaks for all users
            total = BreakManagementService.create_breaks_for_all_users(date)
            self.stdout.write(self.style.SUCCESS(f"Created {total} break logs for all users"))