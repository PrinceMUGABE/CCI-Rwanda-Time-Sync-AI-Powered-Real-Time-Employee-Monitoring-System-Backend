from django.apps import AppConfig
import threading
import time
import sys

class PerformanceAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'performanceApp'
    
    def ready(self):
        """
        Trigger tasks when Django starts
        """
        # Only run when server starts, not during migrations
        if 'runserver' in sys.argv:
            self.trigger_startup_tasks()
    
    def trigger_startup_tasks(self):
        """Run all startup tasks in background"""
        def run_tasks():
            # Wait 5 seconds for everything to initialize
            time.sleep(5)
            
            print("=" * 50)
            print("🚀 PERFORMANCE APP: Running Startup Tasks")
            print("=" * 50)
            
            # Import tasks inside function to avoid circular imports
            from .tasks import (
                create_daily_breaks,
                create_upcoming_breaks,
                check_missed_breaks,
                check_extended_breaks,
                auto_record_scheduled_breaks,
                monitor_and_create_breaks
            )
            
            # Define tasks to run on startup
            tasks = [
                (create_daily_breaks, "📅 Create daily breaks"),
                (create_upcoming_breaks, "⏰ Create upcoming breaks"),
                (check_missed_breaks, "❌ Check missed breaks"),
                (check_extended_breaks, "⏳ Check extended breaks"),
                (auto_record_scheduled_breaks, "📝 Auto-record scheduled breaks"),
                (monitor_and_create_breaks, "👁️ Monitor and create breaks"),
            ]
            
            # Run each task
            for task_func, description in tasks:
                try:
                    # Delay by 1 second between tasks to avoid overwhelming
                    time.sleep(1)
                    
                    # Execute the task
                    result = task_func.delay()
                    print(f"✓ {description} started (ID: {result.id})")
                except Exception as e:
                    print(f"✗ {description} failed: {str(e)}")
            
            print("=" * 50)
            print("✅ All startup tasks triggered successfully!")
            print("=" * 50)
        
        # Run in background thread
        thread = threading.Thread(target=run_tasks, daemon=True)
        thread.start()