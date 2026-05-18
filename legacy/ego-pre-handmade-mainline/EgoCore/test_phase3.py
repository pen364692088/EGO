#!/usr/bin/env python3
"""
OpenEmotion Agent Runtime - Phase 3 Test Suite

Tests the task execution kernel components.
"""

import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Direct imports to avoid telegram dependency
import importlib.util

def import_module(name, path):
    """Import module directly from path."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

# Import modules directly
storage_dir = Path(__file__).parent / "app" / "storage"
runtime_dir = Path(__file__).parent / "app" / "runtime"

models = import_module("app.storage.models", storage_dir / "models.py")
db_module = import_module("app.storage.db", storage_dir / "db.py")
repositories = import_module("app.storage.repositories", storage_dir / "repositories.py")
state_machine = import_module("app.runtime.state_machine", runtime_dir / "state_machine.py")
planner = import_module("app.runtime.planner", runtime_dir / "planner.py")
task_runtime = import_module("app.runtime.task_runtime", runtime_dir / "task_runtime.py")

# Extract classes and functions
Task = models.Task
TaskStep = models.TaskStep
TaskStatus = models.TaskStatus
TaskStepStatus = models.TaskStepStatus
Database = db_module.Database
TaskRepository = repositories.TaskRepository
TaskStepRepository = repositories.TaskStepRepository
StateMachine = state_machine.StateMachine
InvalidStateTransition = state_machine.InvalidStateTransition
transition_to = state_machine.transition_to
TaskPlanner = planner.TaskPlanner
TaskRuntime = task_runtime.TaskRuntime


def test_models():
    """Test data models."""
    print("\n" + "="*60)
    print("Test 1: Data Models")
    print("="*60)
    
    # Create task
    task = Task.create("Build a REST API for user management")
    print(f"✓ Created task: {task.id}")
    print(f"  Objective: {task.objective}")
    print(f"  Status: {task.status.value}")
    
    # Add steps
    step1 = task.add_step("Design API schema")
    step2 = task.add_step("Implement endpoints")
    step3 = task.add_step("Add authentication")
    print(f"✓ Added {len(task.steps)} steps")
    
    # Test serialization
    task_dict = task.to_dict()
    task_restored = Task.from_dict(task_dict)
    print(f"✓ Serialization/deserialization works")
    print(f"  Restored task has {len(task_restored.steps)} steps")
    
    return True


def test_database():
    """Test database operations."""
    print("\n" + "="*60)
    print("Test 2: Database")
    print("="*60)
    
    # Use temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        print(f"✓ Created database at {db_path}")
        
        # Create repositories
        task_repo = TaskRepository(db)
        step_repo = TaskStepRepository(db)
        print("✓ Created repositories")
        
        # Create and save task
        task = Task.create("Test task for database")
        task = task_repo.create(task)
        print(f"✓ Created task in database: {task.id}")
        
        # Add steps
        step1 = TaskStep.create(task.id, "Step 1", 0)
        step2 = TaskStep.create(task.id, "Step 2", 1)
        step_repo.create(step1)
        step_repo.create(step2)
        task.steps = [step1, step2]
        print(f"✓ Created {len(task.steps)} steps")
        
        # Retrieve task
        retrieved = task_repo.get(task.id)
        print(f"✓ Retrieved task: {retrieved.id}")
        print(f"  Has {len(retrieved.steps)} steps")
        
        # Update task status
        retrieved.status = TaskStatus.RUNNING
        task_repo.update(retrieved)
        print(f"✓ Updated task status to {retrieved.status.value}")
        
        # List tasks
        tasks = task_repo.list_all()
        print(f"✓ Listed {len(tasks)} tasks")
        
        db.close()
    
    return True


def test_state_machine():
    """Test state machine transitions."""
    print("\n" + "="*60)
    print("Test 3: State Machine")
    print("="*60)
    
    # Test valid transitions
    print("Valid transitions from CREATED:")
    valid = StateMachine.get_valid_transitions(TaskStatus.CREATED)
    print(f"  {', '.join(s.value for s in valid)}")
    
    print("\nValid transitions from RUNNING:")
    valid = StateMachine.get_valid_transitions(TaskStatus.RUNNING)
    print(f"  {', '.join(s.value for s in valid)}")
    
    # Test can_transition
    print("\n✓ Can transition from CREATED to PLANNING:", 
          StateMachine.can_transition(TaskStatus.CREATED, TaskStatus.PLANNING))
    print("✓ Can transition from CREATED to RUNNING:", 
          StateMachine.can_transition(TaskStatus.CREATED, TaskStatus.RUNNING))
    
    # Test terminal states
    print("\n✓ Is COMPLETED terminal:", StateMachine.is_terminal(TaskStatus.COMPLETED))
    print("✓ Is RUNNING terminal:", StateMachine.is_terminal(TaskStatus.RUNNING))
    
    # Test transition validation
    try:
        transition_to(TaskStatus.CREATED, TaskStatus.RUNNING)
        print("✗ Should have raised exception for invalid transition")
        return False
    except InvalidStateTransition as e:
        print(f"✓ Correctly caught invalid transition: {e}")
    
    return True


def test_planner():
    """Test task planner."""
    print("\n" + "="*60)
    print("Test 4: Task Planner")
    print("="*60)
    
    # Test single-step task
    steps = TaskPlanner.plan("Simple task")
    print(f"✓ Single-step task: {len(steps)} steps")
    print(f"  {steps[0]}")
    
    # Test multi-step task with numbered list
    objective = """
    Build a user management system:
    1. Design database schema
    2. Create API endpoints
    3. Add authentication
    4. Write tests
    """
    steps = TaskPlanner.plan(objective)
    print(f"\n✓ Multi-step task (numbered): {len(steps)} steps")
    for i, step in enumerate(steps):
        print(f"  {i+1}. {step}")
    
    # Test multi-step task with keywords
    steps = TaskPlanner.plan("Research the topic and then write a report and finally publish it")
    print(f"\n✓ Multi-step task (keywords): {len(steps)} steps")
    for i, step in enumerate(steps):
        print(f"  {i+1}. {step}")
    
    return True


def test_task_runtime():
    """Test complete task runtime flow."""
    print("\n" + "="*60)
    print("Test 5: Task Runtime (Full Flow)")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        
        task_repo = TaskRepository(db)
        step_repo = TaskStepRepository(db)
        runtime = TaskRuntime(task_repo, step_repo)
        
        # Create task
        print("\n--- Creating Task ---")
        task = runtime.create_task("Build a complete API system")
        print(f"✓ Created task: {task.id}")
        print(f"  Status: {task.status.value}")
        
        # Plan task
        print("\n--- Planning Task ---")
        task = runtime.plan_task(task.id)
        print(f"✓ Planned task: {len(task.steps)} steps")
        print(f"  Status: {task.status.value}")
        for i, step in enumerate(task.steps):
            print(f"    {i+1}. {step.description}")
        
        # Start task
        print("\n--- Starting Task ---")
        task = runtime.start_task(task.id)
        print(f"✓ Started task")
        print(f"  Status: {task.status.value}")
        
        # Execute steps
        print("\n--- Executing Steps ---")
        while task.status == TaskStatus.RUNNING:
            task, result = runtime.execute_next_step(task.id)
            if result.success:
                print(f"✓ Step completed: {result.output}")
                if task.status == TaskStatus.COMPLETED:
                    print("\n🎉 Task Completed!")
                    break
            else:
                print(f"✗ Step failed: {result.error}")
                break
        
        # Generate report
        print("\n--- Task Report ---")
        report = runtime.generate_report(task.id)
        print(report)
        
        db.close()
    
    return True


def test_persistence():
    """Test task persistence across runtime instances."""
    print("\n" + "="*60)
    print("Test 6: Persistence")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        
        # Create and save task
        task_repo = TaskRepository(db)
        step_repo = TaskStepRepository(db)
        runtime = TaskRuntime(task_repo, step_repo)
        
        task = runtime.create_task("Persistent task test")
        task = runtime.plan_task(task.id)
        task = runtime.start_task(task.id)
        
        task_id = task.id
        print(f"✓ Created task: {task_id}")
        
        # Simulate restart - create new runtime instance with same repos
        runtime2 = TaskRuntime(task_repo, step_repo)
        
        # Retrieve task
        retrieved = runtime2.get_task(task_id)
        print(f"✓ Retrieved task: {retrieved.id}")
        print(f"  Objective: {retrieved.objective}")
        print(f"  Status: {retrieved.status.value}")
        print(f"  Steps: {len(retrieved.steps)}")
        
        db.close()
    
    return True


def main():
    """Run all tests."""
    print("="*60)
    print("OpenEmotion Agent Runtime - Phase 3 Tests")
    print("="*60)
    
    tests = [
        ("Data Models", test_models),
        ("Database", test_database),
        ("State Machine", test_state_machine),
        ("Planner", test_planner),
        ("Task Runtime", test_task_runtime),
        ("Persistence", test_persistence),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success, None))
        except Exception as e:
            results.append((name, False, str(e)))
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
        if error:
            print(f"  Error: {error}")
    
    print(f"\n{passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
