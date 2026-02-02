# performanceApp/management/commands/debug_breaks.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from userApp.models import CustomUser
from shiftApp.models import Shift, BreakTemplate
from performanceApp.models import BreakLog
from performanceApp.services import BreakManagementService


class Command(BaseCommand):
    help = 'Debug why breaks are not being created'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('BREAK CREATION DEBUGGING'))
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))
        
        today = timezone.now().date()
        today_name = timezone.now().strftime('%A').lower()
        
        self.stdout.write(f"Today: {today} ({today_name})\n")
        
        # 1. Check all users
        all_users = CustomUser.objects.all()
        self.stdout.write(f"Total users in database: {all_users.count()}")
        
        # 2. Check active users
        active_users = CustomUser.objects.filter(status='active')
        self.stdout.write(f"Active users: {active_users.count()}")
        
        # 3. Check users with shifts
        users_with_shifts = CustomUser.objects.filter(
            status='active',
            current_shift__isnull=False
        )
        self.stdout.write(f"Active users with shifts: {users_with_shifts.count()}\n")
        
        if users_with_shifts.count() == 0:
            self.stdout.write(self.style.ERROR("❌ NO USERS HAVE SHIFTS ASSIGNED!"))
            self.stdout.write("\nPlease assign shifts to users first.")
            return
        
        # 4. Check users after day_off filter
        users_not_on_day_off = users_with_shifts.exclude(
            day_off=today_name
        )
        self.stdout.write(f"Users not on day off today: {users_not_on_day_off.count()}\n")
        
        # 5. Detailed user information
        self.stdout.write(self.style.SUCCESS('USER DETAILS:\n'))
        for user in users_with_shifts:
            self.stdout.write(f"\n{user.names} (#{user.emp_number})")
            self.stdout.write(f"  Status: {user.status}")
            self.stdout.write(f"  Day off: {user.day_off}")
            self.stdout.write(f"  Is today day off? {user.day_off.lower() == today_name}")
            
            if user.current_shift:
                shift = user.current_shift
                self.stdout.write(f"  Shift: {shift.name} ({shift.start_at} - {shift.end_at})")
                self.stdout.write(f"  Shift status: {shift.status}")
                
                # Check break templates
                break_templates = shift.breaks.filter(status='active')
                self.stdout.write(f"  Break templates: {break_templates.count()}")
                
                if break_templates.count() == 0:
                    self.stdout.write(self.style.WARNING(f"    ⚠ No active break templates for {shift.name}!"))
                else:
                    for bt in break_templates:
                        self.stdout.write(f"    - {bt.name}: {bt.start_at} - {bt.end_at} ({bt.status})")
                
                # Check existing breaks for today
                today_breaks = BreakLog.objects.filter(
                    user=user,
                    scheduled_start__date=today
                )
                self.stdout.write(f"  Existing break logs for today: {today_breaks.count()}")
                
                for bl in today_breaks:
                    self.stdout.write(f"    - {bl.break_template.name}: {bl.status} "
                                    f"({bl.scheduled_start.strftime('%H:%M')} - {bl.scheduled_end.strftime('%H:%M')})")
            else:
                self.stdout.write(self.style.ERROR("  ❌ No shift assigned!"))
        
        # 6. Check all shifts
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('SHIFT INFORMATION'))
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))
        
        shifts = Shift.objects.all()
        self.stdout.write(f"Total shifts: {shifts.count()}\n")
        
        for shift in shifts:
            self.stdout.write(f"\n{shift.name} ({shift.start_at} - {shift.end_at})")
            self.stdout.write(f"  Status: {shift.status}")
            self.stdout.write(f"  Assigned users: {shift.assigned_users.filter(status='active').count()}")
            
            break_templates = shift.breaks.all()
            self.stdout.write(f"  Total break templates: {break_templates.count()}")
            active_breaks = shift.breaks.filter(status='active')
            self.stdout.write(f"  Active break templates: {active_breaks.count()}")
            
            if active_breaks.count() == 0:
                self.stdout.write(self.style.WARNING(f"    ⚠ No active breaks defined!"))
            else:
                for bt in active_breaks:
                    self.stdout.write(f"    - {bt.name}: {bt.start_at} - {bt.end_at}")
        
        # 7. Test break creation
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('TESTING BREAK CREATION'))
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))
        
        self.stdout.write("Running BreakManagementService.create_breaks_for_all_users()...\n")
        
        total = BreakManagementService.create_breaks_for_all_users(today)
        
        self.stdout.write(self.style.SUCCESS(f"\n✓ Result: Created {total} break logs\n"))
        
        # 8. Final summary
        all_breaks_today = BreakLog.objects.filter(scheduled_start__date=today)
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f"\nTotal break logs for {today}: {all_breaks_today.count()}")
        
        if all_breaks_today.count() == 0:
            self.stdout.write(self.style.ERROR("\n❌ NO BREAKS WERE CREATED!"))
            self.stdout.write("\nPossible reasons:")
            self.stdout.write("  1. No users have shifts assigned")
            self.stdout.write("  2. All users are on their day off today")
            self.stdout.write("  3. Shifts have no active break templates")
            self.stdout.write("  4. Users are not in 'active' status")
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✓ {all_breaks_today.count()} breaks created successfully!"))