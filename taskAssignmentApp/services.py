# taskAssignmentApp/services.py (FIXED VERSION)
from django.utils import timezone
from django.db.models import Q, Count
from datetime import datetime, timedelta, time
from .models import TaskAssignment, ShiftTaskRotation, TaskOverload
from performanceApp.models import BreakLog
from userApp.models import CustomUser
from taskApp.models import Task
from shiftApp.models import Shift
import logging

logger = logging.getLogger(__name__)


class TaskAssignmentService:
    """Service for managing task assignments"""
    
    @staticmethod
    def create_daily_assignments(date, shift, assigned_by=None):
        """
        Create task assignments for all employees in a shift for a given date
        This ensures equal distribution and accounts for breaks
        """
        try:
            # Get shift rotation configuration
            rotation = ShiftTaskRotation.objects.filter(
                shift=shift,
                is_active=True
            ).first()
            
            if not rotation:
                logger.warning(f"No active task rotation found for shift {shift.name}")
                return []
            
            # Get tasks for this shift
            tasks = list(rotation.tasks.filter(status='active'))
            
            if not tasks:
                logger.warning(f"No active tasks in rotation for shift {shift.name}")
                return []
            
            
            # Get employees assigned to this shift
            employees = CustomUser.objects.filter(
                current_shift=shift,
                is_active=True,
                status='active',
                role='employee'
            ).exclude(
                # Exclude if it's their day off
                day_off__iexact=date.strftime('%A')
            )
            
            if not employees.exists():
                logger.warning(f"No employees found for shift {shift.name} on {date}")
                return []
            
            # Get shift datetime range
            shift_start, shift_end = shift.get_datetime_range(date)
            
            assignments_created = []
            
            # Create assignments for each employee
            for employee in employees:
                employee_assignments = TaskAssignmentService._create_employee_assignments(
                    employee=employee,
                    date=date,
                    shift=shift,
                    shift_start=shift_start,
                    shift_end=shift_end,
                    tasks=tasks,
                    rotation_interval=rotation.rotation_interval_minutes,
                    assigned_by=assigned_by
                )
                
                assignments_created.extend(employee_assignments)
            
            # Handle task overloads
            TaskAssignmentService._handle_task_overloads(
                date=date,
                shift=shift,
                employees=list(employees),
                assigned_by=assigned_by
            )
            
            logger.info(f"Created {len(assignments_created)} task assignments for {shift.name} on {date}")
            return assignments_created
            
        except Exception as e:
            logger.error(f"Error creating daily assignments: {str(e)}")
            raise
    
    @staticmethod
    def _create_employee_assignments(employee, date, shift, shift_start, shift_end, 
                                     tasks, rotation_interval, assigned_by):
        """Create task assignments for a single employee"""
        assignments = []
        
        # Get employee's breaks for this shift
        employee_breaks = BreakLog.objects.filter(
            user=employee,
            scheduled_start__date=date,
            is_active=True
        ).order_by('scheduled_start')
        
        # Calculate available work periods (excluding breaks)
        work_periods = TaskAssignmentService._calculate_work_periods(
            shift_start, shift_end, employee_breaks
        )
        
        # Distribute tasks across work periods
        task_index = 0
        sequence_order = 1
        
        for period_start, period_end in work_periods:
            period_duration = (period_end - period_start).total_seconds() / 60
            
            # Calculate how many task rotations fit in this period
            num_rotations = int(period_duration / rotation_interval)
            remaining_minutes = period_duration % rotation_interval
            
            current_time = period_start
            
            for rotation in range(num_rotations):
                task = tasks[task_index % len(tasks)]
                
                assignment_start = current_time
                assignment_end = current_time + timedelta(minutes=rotation_interval)
                
                # Ensure we don't exceed period end
                if assignment_end > period_end:
                    assignment_end = period_end
                
                # Create assignment
                assignment = TaskAssignment.objects.create(
                    user=employee,
                    task=task,
                    shift=shift,
                    assignment_date=date,
                    start_time=assignment_start,
                    end_time=assignment_end,
                    sequence_order=sequence_order,
                    assigned_by=assigned_by,
                    status='scheduled'
                )
                
                assignments.append(assignment)
                
                current_time = assignment_end
                task_index += 1
                sequence_order += 1
            
            # Handle remaining time in period
            if remaining_minutes >= 15:  # Only if at least 15 minutes
                task = tasks[task_index % len(tasks)]
                
                assignment = TaskAssignment.objects.create(
                    user=employee,
                    task=task,
                    shift=shift,
                    assignment_date=date,
                    start_time=current_time,
                    end_time=period_end,
                    sequence_order=sequence_order,
                    assigned_by=assigned_by,
                    status='scheduled'
                )
                
                assignments.append(assignment)
                task_index += 1
                sequence_order += 1
        
        return assignments
    
    @staticmethod
    def _calculate_work_periods(shift_start, shift_end, breaks):
        """Calculate work periods excluding breaks"""
        work_periods = []
        current_start = shift_start
        
        for break_log in breaks:
            # Add work period before break
            if current_start < break_log.scheduled_start:
                work_periods.append((current_start, break_log.scheduled_start))
            
            # Move to after break
            current_start = break_log.scheduled_end
        
        # Add final work period after last break
        if current_start < shift_end:
            work_periods.append((current_start, shift_end))
        
        return work_periods
    
    @staticmethod
    def _handle_task_overloads(date, shift, employees, assigned_by):
        """Handle task overload situations by assigning extra employees"""
        overloads = TaskOverload.objects.filter(
            shift=shift,
            overload_date=date,
            is_resolved=False
        )
        
        for overload in overloads:
            # Find employees with lighter task load
            available_employees = sorted(
                employees,
                key=lambda emp: TaskAssignment.objects.filter(
                    user=emp,
                    assignment_date=date,
                    task=overload.task
                ).count()
            )[:overload.additional_employees_needed]
            
            shift_start, shift_end = shift.get_datetime_range(date)
            
            # If specific time slot defined, use it
            if overload.time_slot_start and overload.time_slot_end:
                slot_start = timezone.make_aware(
                    datetime.combine(date, overload.time_slot_start)
                )
                slot_end = timezone.make_aware(
                    datetime.combine(date, overload.time_slot_end)
                )
            else:
                slot_start = shift_start
                slot_end = shift_end
            
            # Assign additional employees to this task
            for employee in available_employees:
                TaskAssignment.objects.create(
                    user=employee,
                    task=overload.task,
                    shift=shift,
                    assignment_date=date,
                    start_time=slot_start,
                    end_time=slot_end,
                    priority='high',
                    assigned_by=assigned_by,
                    status='scheduled',
                    is_modified=True,
                    modification_reason=f"Overload assignment: {overload.reason}"
                )
    
    @staticmethod
    def get_current_assignment(user):
        """Get the current active assignment for a user"""
        now = timezone.now()
        
        return TaskAssignment.objects.filter(
            user=user,
            start_time__lte=now,
            end_time__gte=now,
            status__in=['scheduled', 'active']
        ).first()
    
    @staticmethod
    def get_next_assignment(user):
        """Get the next scheduled assignment for a user"""
        now = timezone.now()
        
        return TaskAssignment.objects.filter(
            user=user,
            start_time__gt=now,
            status='scheduled'
        ).order_by('start_time').first()
    
    @staticmethod
    def get_next_activity(user):
        """
        FIXED: Get next activity (task, break, or shift end)
        Returns: {
            'type': 'task' | 'break' | 'shift_end',
            'object': assignment or break_log or None,
            'start_time': datetime,
            'end_time': datetime,
            'description': str
        }
        """
        now = timezone.now()
        today = now.date()
        
        # Get current assignment
        current_assignment = TaskAssignmentService.get_current_assignment(user)
        
        if current_assignment:
            current_end = current_assignment.end_time
        else:
            current_end = now
        
        # Find next task assignment
        next_task = TaskAssignment.objects.filter(
            user=user,
            start_time__gt=current_end,
            assignment_date=today,
            status='scheduled'
        ).order_by('start_time').first()
        
        # Find next break
        next_break = BreakLog.objects.filter(
            user=user,
            scheduled_start__gt=current_end,
            scheduled_start__date=today,
            is_active=True,
            status__in=['scheduled', 'pending']
        ).order_by('scheduled_start').first()
        
        # Find shift end
        if user.current_shift:
            shift_start, shift_end = user.current_shift.get_datetime_range(today)
            if shift_end > current_end:
                shift_end_activity = {
                    'type': 'shift_end',
                    'object': None,
                    'start_time': shift_end,
                    'end_time': shift_end,
                    'description': f'End of {user.current_shift.name}'
                }
            else:
                shift_end_activity = None
        else:
            shift_end_activity = None
        
        # Determine which comes first
        candidates = []
        
        if next_task:
            candidates.append({
                'type': 'task',
                'object': next_task,
                'start_time': next_task.start_time,
                'end_time': next_task.end_time,
                'description': f'Task: {next_task.task.name}'
            })
        
        if next_break:
            candidates.append({
                'type': 'break',
                'object': next_break,
                'start_time': next_break.scheduled_start,
                'end_time': next_break.scheduled_end,
                'description': f'Break: {next_break.break_template.name}'
            })
        
        if shift_end_activity:
            candidates.append(shift_end_activity)
        
        if not candidates:
            return None
        
        # Return the earliest activity
        return min(candidates, key=lambda x: x['start_time'])
    
    @staticmethod
    def modify_assignment(assignment_id, modified_by, new_task_id=None, 
                         new_start_time=None, new_end_time=None, reason=None):
        """Modify an existing assignment"""
        try:
            assignment = TaskAssignment.objects.get(id=assignment_id)
            
            # Check permissions
            if not TaskAssignmentService._can_modify_assignment(modified_by, assignment.user):
                raise PermissionError("You don't have permission to modify this assignment")
            
            changes_made = []
            
            # Update task
            if new_task_id and new_task_id != assignment.task.id:
                old_task = assignment.task
                assignment.task = Task.objects.get(id=new_task_id)
                changes_made.append(f"Task changed from {old_task.name} to {assignment.task.name}")
            
            # Update times
            if new_start_time and new_start_time != assignment.start_time:
                changes_made.append(f"Start time changed from {assignment.start_time} to {new_start_time}")
                assignment.start_time = new_start_time
            
            if new_end_time and new_end_time != assignment.end_time:
                changes_made.append(f"End time changed from {assignment.end_time} to {new_end_time}")
                assignment.end_time = new_end_time
            
            if changes_made:
                assignment.is_modified = True
                assignment.modified_by = modified_by
                assignment.modification_reason = reason or "; ".join(changes_made)
                assignment.save()
                
                # Send notification to employee
                TaskAssignmentService._send_modification_notification(assignment, changes_made)
                
                logger.info(f"Assignment {assignment_id} modified by {modified_by.emp_number}")
            
            return assignment
            
        except TaskAssignment.DoesNotExist:
            raise ValueError("Assignment not found")
        except Task.DoesNotExist:
            raise ValueError("Task not found")
    
    @staticmethod
    def _can_modify_assignment(user, assignment_user):
        """Check if user can modify assignment"""
        if user.is_admin:
            return True
        
        if user.is_supervisor:
            return user.can_supervise(assignment_user)
        
        return False
    
    @staticmethod
    def _send_modification_notification(assignment, changes):
        """Send notification about assignment modification"""
        try:
            from notificationApp.models import Notification
            
            message = f"Your task assignment has been modified:\n" + "\n".join(changes)
            
            Notification.objects.create(
                user=assignment.user,
                notification_type='system_alert',
                title='Task Assignment Modified',
                message=message,
                priority='high',
                action_url=f'/assignments/{assignment.id}/',
                action_text='View Assignment',
                metadata={
                    'assignment_id': assignment.id,
                    'task_name': assignment.task.name,
                    'modified_by': assignment.modified_by.emp_number if assignment.modified_by else None
                }
            ).mark_as_sent()
            
        except Exception as e:
            logger.error(f"Failed to send modification notification: {str(e)}")


    @staticmethod
    def mark_assignment_as_missed(assignment_id):
        """Mark assignment as missed and send notifications"""
        from notificationApp.services import NotificationService
        
        assignment = TaskAssignment.objects.get(id=assignment_id)
        assignment.status = 'missed'
        assignment.save()
        
        # Send immediate notification to supervisors/admins
        NotificationService.create_task_missed_alert(assignment)
        
        return assignment


class TaskNotificationService:
    """FIXED: Service for sending task-related notifications at 30, 15, 10, 5 minutes"""
    
    # FIXED: Support multiple reminder times
    REMINDER_MINUTES = [30, 15, 10, 5]
    
    @staticmethod
    def send_task_reminders():
        """
        FIXED: Send reminders at 30, 15, 10, and 5 minutes before activity ends
        """
        now = timezone.now()
        
        for minutes in TaskNotificationService.REMINDER_MINUTES:
            reminder_time = now + timedelta(minutes=minutes)
            
            # Get assignments ending in exactly this time window (±1 minute tolerance)
            window_start = reminder_time - timedelta(minutes=1)
            window_end = reminder_time + timedelta(minutes=1)
            
            upcoming_assignments = TaskAssignment.objects.filter(
                status='active',
                end_time__gte=window_start,
                end_time__lte=window_end
            ).select_related('user', 'task', 'shift')
            
            for assignment in upcoming_assignments:
                # Check if reminder already sent for this time interval
                reminder_key = f"{assignment.id}_{minutes}min"
                
                # Use metadata to track sent reminders
                if not assignment.metadata:
                    assignment.metadata = {}
                
                sent_reminders = assignment.metadata.get('sent_reminders', [])
                
                if reminder_key not in sent_reminders:
                    # Get next activity
                    next_activity = TaskAssignmentService.get_next_activity(assignment.user)
                    
                    TaskNotificationService._send_task_reminder(
                        assignment=assignment,
                        minutes_remaining=minutes,
                        next_activity=next_activity
                    )
                    
                    # Mark this reminder as sent
                    sent_reminders.append(reminder_key)
                    assignment.metadata['sent_reminders'] = sent_reminders
                    assignment.save(update_fields=['metadata'])
    
    @staticmethod
    def _send_task_reminder(assignment, minutes_remaining, next_activity):
        """
        FIXED: Send reminder with info about what comes next
        """
        try:
            from notificationApp.models import Notification
            
            # Build message based on what's next
            if next_activity:
                if next_activity['type'] == 'task':
                    next_info = f"Next up: {next_activity['description']} at {next_activity['start_time'].strftime('%H:%M')}"
                elif next_activity['type'] == 'break':
                    next_info = f"Next: {next_activity['description']} at {next_activity['start_time'].strftime('%H:%M')}"
                elif next_activity['type'] == 'shift_end':
                    next_info = f"Next: {next_activity['description']} at {next_activity['start_time'].strftime('%H:%M')}"
                else:
                    next_info = "This is your last task for today"
            else:
                next_info = "This is your last task for today"
            
            message = (
                f"⏰ {minutes_remaining} minutes remaining on {assignment.task.name}.\n\n"
                f"{next_info}"
            )
            
            # Set priority based on time remaining
            if minutes_remaining <= 5:
                priority = 'high'
            elif minutes_remaining <= 10:
                priority = 'medium'
            else:
                priority = 'low'
            
            Notification.objects.create(
                user=assignment.user,
                notification_type='system_alert',
                title=f'{minutes_remaining} Minutes Remaining',
                message=message,
                priority=priority,
                action_url='/assignments/current/',
                action_text='View Schedule',
                metadata={
                    'current_task': assignment.task.name,
                    'minutes_remaining': minutes_remaining,
                    'next_activity_type': next_activity['type'] if next_activity else None,
                    'next_activity_time': next_activity['start_time'].isoformat() if next_activity else None
                }
            ).mark_as_sent()
            
            logger.info(
                f"Sent {minutes_remaining}-minute reminder to {assignment.user.emp_number} "
                f"for task {assignment.task.name}"
            )
            
        except Exception as e:
            logger.error(f"Failed to send task reminder: {str(e)}")
    
    @staticmethod
    def check_missed_assignments():
        """Mark assignments as missed if not started on time"""
        now = timezone.now()
        
        missed_assignments = TaskAssignment.objects.filter(
            status='scheduled',
            end_time__lt=now - timedelta(minutes=5)
        )
        
        count = 0
        for assignment in missed_assignments:
            assignment.status = 'missed'
            assignment.save()
            
            # Create user log
            from userApp.models import UserLog
            UserLog.objects.create(
                user=assignment.user,
                log_type='system_event',
                status='absent',
                activity=f"Missed task: {assignment.task.name}",
                scheduled_time=assignment.start_time,
                shift=assignment.shift,
                is_auto_generated=True,
                notes=f"Task was not started. Assignment ID: {assignment.id}"
            )
            
            count += 1
        
        if count > 0:
            logger.info(f"Marked {count} assignments as missed")
        
        return count