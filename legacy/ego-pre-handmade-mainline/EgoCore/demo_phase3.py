#!/usr/bin/env python3
"""
OpenEmotion Agent Runtime - Phase 3 Demo

Demonstrates the task execution kernel capabilities.
"""

import sys
from pathlib import Path

# Direct imports
import importlib.util

def import_module(name, path):
    """Import module directly from path."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

# Import modules
storage_dir = Path(__file__).parent / "app" / "storage"
runtime_dir = Path(__file__).parent / "app" / "runtime"

models = import_module("app.storage.models", storage_dir / "models.py")
db_module = import_module("app.storage.db", storage_dir / "db.py")
repositories = import_module("app.storage.repositories", storage_dir / "repositories.py")
task_runtime = import_module("app.runtime.task_runtime", runtime_dir / "task_runtime.py")

# Extract classes
Task = models.Task
TaskStatus = models.TaskStatus
Database = db_module.Database
TaskRepository = repositories.TaskRepository
TaskStepRepository = repositories.TaskStepRepository
TaskRuntime = task_runtime.TaskRuntime


def print_header(title):
    """Print formatted header."""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)


def main():
    """Run demo."""
    print_header("OpenEmotion Agent Runtime - Phase 3 Demo")
    print("\nThis demo showcases the task execution kernel capabilities:")
    print("• Create tasks")
    print("• Plan tasks (decompose into steps)")
    print("• Execute tasks step by step")
    print("• Track status changes")
    print("• Generate reports")
    
    # Use default database location
    db = Database()
    task_repo = TaskRepository(db)
    step_repo = TaskStepRepository(db)
    runtime = TaskRuntime(task_repo, step_repo)
    
    print_header("1. Creating a Task")
    objective = """
    Build a user management system:
    1. Design database schema
    2. Create API endpoints
    3. Add authentication
    4. Write tests
    """
    
    task = runtime.create_task(objective.strip())
    print(f"✓ Created task: {task.id}")
    print(f"  Objective: {task.objective[:60]}...")
    print(f"  Status: {task.status.value}")
    
    print_header("2. Planning the Task")
    task = runtime.plan_task(task.id)
    print(f"✓ Task decomposed into {len(task.steps)} steps:")
    for i, step in enumerate(task.steps):
        print(f"  {i+1}. {step.description}")
    
    print_header("3. Starting the Task")
    task = runtime.start_task(task.id)
    print(f"✓ Task started")
    print(f"  Status: {task.status.value}")
    
    print_header("4. Executing Steps")
    step_num = 1
    while task.status == TaskStatus.RUNNING:
        print(f"\n--- Executing Step {step_num} ---")
        task, result = runtime.execute_next_step(task.id)
        
        if result.success:
            print(f"✓ Step completed: {result.output[:80]}...")
            step_num += 1
            
            if task.status == TaskStatus.COMPLETED:
                print("\n🎉 All steps completed!")
                break
        else:
            print(f"✗ Step failed: {result.error}")
            break
    
    print_header("5. Task Status Summary")
    completed, total = task.progress
    print(f"Task ID: {task.id}")
    print(f"Status: {task.status.value.upper()}")
    print(f"Progress: {completed}/{total} steps ({task.progress_percentage:.0f}%)")
    
    print_header("6. Task Report")
    report = runtime.generate_report(task.id)
    print(report)
    
    print_header("7. List All Tasks")
    tasks = runtime.list_tasks(limit=10)
    print(f"Total tasks: {len(tasks)}")
    for t in tasks[-3:]:  # Show last 3
        c, tot = t.progress
        print(f"  • {t.id}: {t.status.value} ({c}/{tot} steps)")
    
    print_header("Demo Complete!")
    print("\n✅ Phase 3 Task Execution Kernel is fully functional!")
    print("\nKey features implemented:")
    print("✓ Task and TaskStep data models")
    print("✓ SQLite database with repositories")
    print("✓ Task state machine")
    print("✓ Simple task planner")
    print("✓ Step-by-step execution")
    print("✓ Status tracking and reporting")
    
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
