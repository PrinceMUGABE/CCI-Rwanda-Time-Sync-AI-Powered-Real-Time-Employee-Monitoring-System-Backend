# taskAssignmentApp/services.py (ENHANCED VERSION)
from django.utils import timezone
from django.db.models import Q, Count, Avg
from datetime import datetime, timedelta, time
import random
from collections import defaultdict
from .models import TaskAssignment, ShiftTaskRotation, TaskOverload
from performanceApp.models import BreakLog
from userApp.models import CustomUser
from taskApp.models import Task
from shiftApp.models import Shift
import logging

logger = logging.getLogger(__name__)


class TaskAssignmentService:
    """Service for managing task assignments with intelligent rotation"""
    
    @staticmethod
    def create_daily_assignments(date, shift, assigned_by=None):
        """
        Create task assignments for all employees in a shift for a given date
        This ensures equal distribution, random rotation, and accounts for breaks
        
        Scenario: 30 employees, 5 tasks, 50-minute rotation
        - Each task should have ~6 employees at any given time
        - Employees should rotate randomly between tasks
        - Ensure all employees get equal task distribution over time
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
            employees = list(CustomUser.objects.filter(
                current_shift=shift,
                is_active=True,
                status='active',
                role='employee'
            ).exclude(
                # Exclude if it's their day off
                day_off__iexact=date.strftime('%A')
            ).order_by('id'))
            
            if not employees:
                logger.warning(f"No employees found for shift {shift.name} on {date}")
                return []
            
            # Get shift datetime range
            shift_start, shift_end = shift.get_datetime_range(date)
            
            # Get employee breaks
            employee_breaks = TaskAssignmentService._get_employee_breaks(employees, date)
            
            # Calculate optimal rotation pattern
            assignments = TaskAssignmentService._create_rotating_assignments(
                employees=employees,
                tasks=tasks,
                shift_start=shift_start,
                shift_end=shift_end,
                rotation_interval=rotation.rotation_interval_minutes,
                employee_breaks=employee_breaks,
                assigned_by=assigned_by,
                date=date,
                shift=shift
            )
            
            # Handle task overloads
            TaskAssignmentService._handle_task_overloads(
                date=date,
                shift=shift,
                employees=employees,
                assigned_by=assigned_by
            )
            
            logger.info(f"Created {len(assignments)} task assignments for {shift.name} on {date}")
            logger.info(f"Distribution: {len(employees)} employees, {len(tasks)} tasks, {rotation.rotation_interval_minutes}min rotations")
            
            return assignments
            
        except Exception as e:
            logger.error(f"Error creating daily assignments: {str(e)}")
            raise
    
    @staticmethod
    def _get_employee_breaks(employees, date):
        """Get all breaks for employees on the given date"""
        breaks = {}
        for employee in employees:
            employee_breaks = list(BreakLog.objects.filter(
                user=employee,
                scheduled_start__date=date,
                is_active=True
            ).order_by('scheduled_start'))
            breaks[employee.id] = employee_breaks
        return breaks
    
    @staticmethod
    def _create_rotating_assignments(employees, tasks, shift_start, shift_end, 
                                     rotation_interval, employee_breaks, assigned_by, date, shift):
        """
        Create rotating assignments with random task distribution
        
        Strategy:
        1. Calculate number of employees needed per task
        2. Create rotation slots across the entire shift
        3. Randomly assign employees to slots ensuring variety
        4. Respect break times
        """
        assignments = []
        
        # Calculate shift duration in minutes
        shift_duration_minutes = int((shift_end - shift_start).total_seconds() / 60)
        
        # Calculate number of rotation slots
        num_slots = shift_duration_minutes // rotation_interval
        if shift_duration_minutes % rotation_interval > 15:  # Add partial slot if >15min
            num_slots += 1
        
        # Calculate employees needed per task per slot
        employees_per_task = len(employees) // len(tasks)
        remainder = len(employees) % len(tasks)
        
        logger.info(f"Shift: {num_slots} slots, {employees_per_task}+{remainder} employees per task")
        
        # Track assignment history for each employee
        employee_history = defaultdict(list)  # employee_id -> list of task_ids
        
        # Create time slots
        for slot_index in range(num_slots):
            slot_start = shift_start + timedelta(minutes=slot_index * rotation_interval)
            slot_end = min(
                slot_start + timedelta(minutes=rotation_interval),
                shift_end
            )
            
            # Skip if slot is too short (< 15 minutes)
            if (slot_end - slot_start).total_seconds() / 60 < 15:
                continue
            
            # Determine task distribution for this slot
            task_distribution = []
            available_tasks = tasks.copy()
            
            # Distribute employees across tasks
            for task_index, task in enumerate(available_tasks):
                # Calculate how many employees for this task
                if task_index < remainder:
                    num_for_task = employees_per_task + 1
                else:
                    num_for_task = employees_per_task
                
                task_distribution.append({
                    'task': task,
                    'count': num_for_task,
                    'assigned': []
                })
            
            # Randomly assign employees to tasks for this slot
            available_employees = employees.copy()
            
            # Prioritize employees who haven't done certain tasks recently
            for task_info in task_distribution:
                task = task_info['task']
                needed = task_info['count']
                
                if needed > 0 and available_employees:
                    # Score employees based on how recently they did this task
                    scored_employees = []
                    for emp in available_employees:
                        # Count how many times they've done this task
                        task_count = sum(1 for t in employee_history[emp.id] if t == task.id)
                        
                        # Lower score = higher priority (to balance distribution)
                        score = task_count * 10 + random.random()
                        scored_employees.append((score, emp))
                    
                    # Sort by score (lowest first)
                    scored_employees.sort(key=lambda x: x[0])
                    
                    # Select needed employees
                    selected = []
                    for i in range(min(needed, len(scored_employees))):
                        emp = scored_employees[i][1]
                        selected.append(emp)
                        # Update history
                        employee_history[emp.id].append(task.id)
                    
                    task_info['assigned'] = selected
                    
                    # Remove selected employees from available pool
                    for emp in selected:
                        available_employees.remove(emp)
            
            # Create assignments for this slot
            for task_info in task_distribution:
                task = task_info['task']
                for employee in task_info['assigned']:
                    # Check if employee is on break during this slot
                    if TaskAssignmentService._is_on_break(employee, slot_start, slot_end, employee_breaks):
                        # Skip this slot for this employee
                        continue
                    
                    # Create assignment
                    assignment = TaskAssignment.objects.create(
                        user=employee,
                        task=task,
                        shift=shift,
                        assignment_date=date,
                        start_time=slot_start,
                        end_time=slot_end,
                        sequence_order=len(assignments) + 1,
                        assigned_by=assigned_by,
                        status='scheduled',
                        metadata={
                            'slot_index': slot_index,
                            'rotation_type': 'random'
                        }
                    )
                    
                    assignments.append(assignment)
        
        # Verify distribution and log stats
        TaskAssignmentService._log_assignment_stats(assignments, employees, tasks)
        
        return assignments
    
    @staticmethod
    def _is_on_break(employee, slot_start, slot_end, employee_breaks):
        """Check if employee has a break during the given time slot"""
        if employee.id not in employee_breaks:
            return False
        
        for break_log in employee_breaks[employee.id]:
            # Check if break overlaps with slot
            if (break_log.scheduled_start < slot_end and 
                break_log.scheduled_end > slot_start):
                return True
        
        return False
    
    @staticmethod
    def _log_assignment_stats(assignments, employees, tasks):
        """Log statistics about the assignments created"""
        try:
            # Count assignments per employee
            emp_counts = defaultdict(int)
            task_counts = defaultdict(int)
            
            for assignment in assignments:
                emp_counts[assignment.user.id] += 1
                task_counts[assignment.task.id] += 1
            
            # Calculate averages
            avg_emp = sum(emp_counts.values()) / len(employees) if employees else 0
            avg_task = sum(task_counts.values()) / len(tasks) if tasks else 0
            
            logger.info(f"Assignment Statistics:")
            logger.info(f"  Total assignments: {len(assignments)}")
            logger.info(f"  Avg per employee: {avg_emp:.2f}")
            logger.info(f"  Avg per task: {avg_task:.2f}")
            logger.info(f"  Employee range: {min(emp_counts.values()) if emp_counts else 0} - {max(emp_counts.values()) if emp_counts else 0}")
            logger.info(f"  Task range: {min(task_counts.values()) if task_counts else 0} - {max(task_counts.values()) if task_counts else 0}")
            
        except Exception as e:
            logger.error(f"Error logging assignment stats: {str(e)}")
    
    @staticmethod
    def get_optimal_task_distribution(employees, tasks, rotation_interval, shift_duration_minutes):
        """
        Calculate optimal task distribution based on scenario
        
        Returns: dict with distribution plan
        """
        num_employees = len(employees)
        num_tasks = len(tasks)
        
        # Calculate number of rotation slots
        num_slots = shift_duration_minutes // rotation_interval
        if shift_duration_minutes % rotation_interval > 15:
            num_slots += 1
        
        # Calculate base distribution
        employees_per_task_base = num_employees // num_tasks
        remainder = num_employees % num_tasks
        
        # Calculate total assignments needed
        total_assignments = num_slots * num_employees
        
        # Calculate assignments per task
        assignments_per_task = total_assignments // num_tasks
        task_remainder = total_assignments % num_tasks
        
        return {
            'num_employees': num_employees,
            'num_tasks': num_tasks,
            'num_slots': num_slots,
            'employees_per_task_base': employees_per_task_base,
            'remainder_employees': remainder,
            'total_assignments': total_assignments,
            'assignments_per_task': assignments_per_task,
            'task_remainder': task_remainder,
            'strategy': f"{employees_per_task_base}+{remainder} employees per task, "
                       f"{assignments_per_task}+{task_remainder} assignments per task"
        }
    
    @staticmethod
    def _create_employee_assignments(employee, date, shift, shift_start, shift_end, 
                                     tasks, rotation_interval, assigned_by):
        """Original method kept for backward compatibility"""
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
        
        # Distribute tasks across work periods with random selection
        sequence_order = 1
        
        for period_start, period_end in work_periods:
            period_duration = (period_end - period_start).total_seconds() / 60
            
            # Calculate how many task rotations fit in this period
            num_rotations = int(period_duration / rotation_interval)
            remaining_minutes = period_duration % rotation_interval
            
            current_time = period_start
            
            # Create rotation list for this period
            rotation_tasks = tasks.copy()
            random.shuffle(rotation_tasks)  # Randomize task order
            
            for rotation in range(num_rotations):
                task = rotation_tasks[rotation % len(rotation_tasks)]
                
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
                sequence_order += 1
            
            # Handle remaining time in period
            if remaining_minutes >= 15:  # Only if at least 15 minutes
                task = random.choice(tasks)  # Random task for remainder
                
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
        Get next activity (task, break, or shift end)
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
    
    @staticmethod
    def get_task_distribution_summary(assignments, employees, tasks):
        """
        Get summary of how tasks are distributed
        """
        summary = {
            'total_assignments': len(assignments),
            'employees': len(employees),
            'tasks': len(tasks),
            'employee_distribution': {},
            'task_distribution': {},
            'rotation_patterns': []
        }
        
        # Count per employee
        emp_counts = defaultdict(int)
        for a in assignments:
            emp_counts[a.user.id] += 1
        
        # Count per task
        task_counts = defaultdict(int)
        for a in assignments:
            task_counts[a.task.id] += 1
        
        # Analyze rotation patterns
        assignments_by_employee = defaultdict(list)
        for a in assignments:
            assignments_by_employee[a.user.id].append(a)
        
        for emp_id, emp_assignments in assignments_by_employee.items():
            # Sort by start time
            emp_assignments.sort(key=lambda x: x.start_time)
            
            # Track task changes
            task_sequence = [a.task.id for a in emp_assignments]
            changes = sum(1 for i in range(1, len(task_sequence)) if task_sequence[i] != task_sequence[i-1])
            
            summary['rotation_patterns'].append({
                'employee_id': emp_id,
                'total_assignments': len(emp_assignments),
                'task_changes': changes,
                'unique_tasks': len(set(task_sequence))
            })
        
        summary['employee_distribution'] = dict(emp_counts)
        summary['task_distribution'] = dict(task_counts)
        
        return summary


class TaskNotificationService:
    """Service for sending task-related notifications at 30, 15, 10, 5 minutes"""
    
    REMINDER_MINUTES = [30, 15, 10, 5]
    
    @staticmethod
    def send_task_reminders():
        """
        Send reminders at 30, 15, 10, and 5 minutes before activity ends
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
        Send reminder with info about what comes next
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