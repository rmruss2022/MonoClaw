# Orchestrator Example: How I (OpenClaw) Manage Projects

This document shows how the main agent (me) orchestrates agent swarms using the kanban dashboard.

## 🎯 User Request

```
You: "Build an iOS app similar to o-p-e-n.com/everywhere.
     Focus on banking integration and spending insights.
     Target: 2 weeks for MVP."
```

## 🤖 My Orchestration Steps

### Step 1: Initialize Project

```python
import os
import sys
sys.path.append('/Users/matthew/.openclaw/workspace/agent-swarm-template')
from kanban_manager import KanbanManager

# Create project directory
project_dir = "/Users/matthew/workspace/projects/ios-banking-app"
os.makedirs(project_dir, exist_ok=True)

# Copy template files
import shutil
template = "/Users/matthew/.openclaw/workspace/agent-swarm-template"
shutil.copy(f"{template}/dashboard.html", project_dir)
shutil.copy(f"{template}/kanban_manager.py", project_dir)

# Initialize kanban
kanban = KanbanManager(project_dir)
kanban.set_project_info(
    "iOS Banking App",
    "Agent swarm building iOS app similar to o-p-e-n.com/everywhere with banking integration and spending insights",
    "https://o-p-e-n.com/everywhere"
)
```

### Step 2: Spawn Product Agent for Discovery

```python
# Spawn Product Agent to analyze requirements
result = sessions_spawn(
    task="""Analyze o-p-e-n.com/everywhere and create a comprehensive PRD.

Research:
- Core features (banking integration, spending insights, notifications)
- User flows (onboarding, linking accounts, viewing insights)
- Technical requirements (APIs needed, data models)
- UI/UX patterns

Create:
1. Feature breakdown (20-30 features)
2. User stories with acceptance criteria
3. Technical architecture recommendations
4. Priority ranking (MVP vs nice-to-have)

Write PRD to: {project_dir}/specs/PRD.md

Format as structured markdown with clear sections.""",
    label="Product-Discovery",
    model="anthropic/claude-sonnet-4-5",
    thinking="high",
    runTimeoutSeconds=600
)

# Log the spawn
kanban._log_activity("product-agent", None, "Spawned Product Agent for discovery", "spawn")
```

### Step 3: Process Product Agent Results

```python
# When Product Agent announces completion, I parse the result:
# "PRD complete at specs/PRD.md. Identified 25 features across 5 categories."

# Read the PRD
with open(f"{project_dir}/specs/PRD.md", 'r') as f:
    prd_content = f.read()

# Extract features (simplified - would use LLM to parse)
features = [
    {"title": "User Authentication", "priority": "high", "hours": 4, "category": "auth"},
    {"title": "Bank Account Linking", "priority": "high", "hours": 6, "category": "banking"},
    {"title": "Transaction Sync", "priority": "high", "hours": 8, "category": "data"},
    {"title": "Spending Insights Dashboard", "priority": "high", "hours": 8, "category": "ui"},
    {"title": "Push Notifications", "priority": "medium", "hours": 4, "category": "features"},
    # ... more features
]

# Create tasks in kanban
for feature in features:
    kanban.add_task(
        title=feature["title"],
        description=f"From PRD: {feature['category']} feature",
        priority=feature["priority"],
        estimated_hours=feature["hours"],
        tags=[feature["category"], "ios"]
    )

# Mark discovery complete
kanban._log_activity("orchestrator", None, 
                     f"Created {len(features)} tasks from PRD", "info")
```

### Step 4: Spawn Spec Agents for High-Priority Tasks

```python
# Get high-priority tasks that need specs
high_priority = [t for t in kanban.get_all_tasks() 
                 if t["priority"] == "high" and t["state"] == "todo"]

for task in high_priority[:5]:  # Start with first 5
    result = sessions_spawn(
        task=f"""Write detailed specification for: {task['title']}

Based on PRD at {project_dir}/specs/PRD.md, create a detailed spec covering:

1. User Stories
   - As a [user], I want [goal] so that [benefit]
   - Acceptance criteria for each story

2. Technical Requirements
   - API endpoints needed
   - Data models
   - Third-party integrations

3. UI/UX Specification
   - Screen mockups (text descriptions)
   - User flow diagrams
   - Interaction patterns

4. Edge Cases
   - Error handling
   - Offline behavior
   - Loading states

5. Testing Criteria
   - Unit test requirements
   - Integration test scenarios
   - Manual QA checklist

Write to: {project_dir}/specs/{task['id']}.md

Be thorough but concise. Focus on what a developer needs to implement this.""",
        label=f"Product-{task['id']}",
        model="anthropic/claude-sonnet-4-5",
        runTimeoutSeconds=300
    )
    
    # Update kanban
    kanban.update_task_state(task["id"], "in-progress", "Spec being written")
    kanban.assign_agent(task["id"], f"product-{task['id']}", result["childSessionKey"])
```

### Step 5: Process Spec Completions & Spawn Dev Agents

```python
# When Product Agent announces: "Spec complete for task-1 at specs/task-1.md"

def handle_spec_completion(task_id: str, spec_file: str):
    # Update task
    kanban.add_task_file(task_id, "spec", spec_file)
    kanban.update_task_state(task_id, "ready", "Spec complete, ready for development")
    kanban.agent_completed(f"product-{task_id}", task_id, f"Spec written to {spec_file}")
    
    # Spawn Dev Agent
    task = kanban._find_task(task_id)
    result = sessions_spawn(
        task=f"""Implement: {task['title']}

Specification: {project_dir}/{spec_file}

Requirements:
1. Read the spec thoroughly
2. Implement all features with clean, idiomatic Swift
3. Follow iOS best practices and Human Interface Guidelines
4. Write unit tests for business logic
5. Add inline documentation
6. Handle all edge cases from spec

Write code to: {project_dir}/src/{task_id}/
Write tests to: {project_dir}/tests/{task_id}/

When complete, provide:
- List of files created
- Brief implementation notes
- Any deviations from spec (with justification)""",
        label=f"Dev-{task_id}",
        model="anthropic/claude-sonnet-4-5",
        thinking="high",
        runTimeoutSeconds=1800  # 30 min for implementation
    )
    
    kanban.update_task_state(task_id, "in-progress", "Development started")
    kanban.assign_agent(task_id, f"dev-{task_id}", result["childSessionKey"])

# Handle announcement
handle_spec_completion("task-1", "specs/task-1.md")
```

### Step 6: Process Dev Completions & Spawn QA Agents

```python
def handle_dev_completion(task_id: str, files: list):
    # Update task
    for file in files:
        kanban.add_task_file(task_id, "code", file)
    
    kanban.update_task_state(task_id, "qa", "Code complete, ready for QA")
    kanban.agent_completed(f"dev-{task_id}", task_id, 
                          f"Implementation complete: {len(files)} files")
    
    # Spawn QA Agent
    task = kanban._find_task(task_id)
    result = sessions_spawn(
        task=f"""Test and verify: {task['title']}

Specification: {project_dir}/{task['spec_file']}
Code location: {project_dir}/src/{task_id}/
Tests location: {project_dir}/tests/{task_id}/

QA Tasks:
1. Review code against spec - verify all requirements met
2. Run all unit tests - ensure 100% pass
3. Manual testing - follow test scenarios from spec
4. Edge case verification - test error handling, edge cases
5. Code quality check - readability, documentation, best practices

Create test report at: {project_dir}/qa-reports/{task_id}.md

Report should include:
- ✅ Requirements met / ❌ Requirements missing
- Test results (all passed/failed tests)
- Bugs found (with severity)
- Code quality notes
- Final verdict: PASS or FAIL

If FAIL, list specific issues that need fixing.""",
        label=f"QA-{task_id}",
        model="anthropic/claude-sonnet-4-5",
        runTimeoutSeconds=600
    )
    
    kanban.assign_agent(task_id, f"qa-{task_id}", result["childSessionKey"])

# Handle dev announcement
handle_dev_completion("task-1", ["src/task-1/auth.swift", "tests/task-1/test_auth.swift"])
```

### Step 7: Process QA Results

```python
def handle_qa_completion(task_id: str, verdict: str, issues: list):
    if verdict == "PASS":
        kanban.update_task_state(task_id, "complete", "All tests passed ✅")
        kanban.agent_completed(f"qa-{task_id}", task_id, "QA passed - ready for production")
        
        # Check if this unblocked any dependent tasks
        for task in kanban.get_all_tasks():
            if task_id in task["dependencies"] and task["state"] == "todo":
                ready = all(
                    kanban._find_task(dep)["state"] == "complete" 
                    for dep in task["dependencies"]
                )
                if ready:
                    kanban.update_task_state(task["id"], "ready", 
                                           "Dependencies met, ready for spec")
    else:
        # QA failed - send back to dev
        kanban.update_task_state(task_id, "in-progress", f"QA failed: {len(issues)} issues")
        kanban.agent_completed(f"qa-{task_id}", task_id, f"QA failed - {len(issues)} issues found")
        
        # Optionally: spawn dev agent again with issues list
        # ... (similar to Step 5 but include issues in prompt)

# Handle QA announcement
handle_qa_completion("task-1", "PASS", [])
```

### Step 8: Monitor Progress & Iterate

```python
# Every time I receive an agent announcement, I:

def on_agent_announcement(agent_id: str, task_id: str, message: str):
    """Called when any agent completes and announces result."""
    
    # Determine agent type from ID
    if "product-" in agent_id:
        # Extract spec file from message
        spec_file = extract_spec_file(message)
        handle_spec_completion(task_id, spec_file)
    
    elif "dev-" in agent_id:
        # Extract file list from message
        files = extract_files(message)
        handle_dev_completion(task_id, files)
    
    elif "qa-" in agent_id:
        # Extract verdict and issues from message
        verdict, issues = extract_qa_result(message)
        handle_qa_completion(task_id, verdict, issues)
    
    # Check if project is complete
    stats = kanban.get_stats()
    if stats["completed"] == stats["total_tasks"]:
        # All done!
        kanban._log_activity("orchestrator", None, 
                           "🎉 Project complete! All tasks finished.", "info")
        
        # Announce to user
        return f"""✅ Project Complete!

{stats['total_tasks']} tasks completed in {calculate_elapsed_time()} hours.

Dashboard: {project_dir}/dashboard.html
Code: {project_dir}/src/
Tests: {project_dir}/tests/

All features implemented and tested. Ready for integration!"""

# This runs automatically as agents complete
```

## 🎮 Full Automation Loop

```python
# This is my main orchestration loop that runs continuously:

def orchestrate_project(project_dir: str):
    """Main orchestration loop."""
    kanban = KanbanManager(project_dir)
    
    while True:
        # 1. Check for ready tasks (specs complete, deps met)
        ready_tasks = kanban.get_ready_tasks()
        for task in ready_tasks[:3]:  # Max 3 dev agents at once
            spawn_dev_agent(task)
        
        # 2. Check for todo tasks that need specs
        todo_tasks = kanban.get_todo_tasks()
        for task in todo_tasks[:2]:  # Max 2 product agents at once
            spawn_product_agent(task)
        
        # 3. Wait for agent announcements
        # (This is handled by OpenClaw's announcement system automatically)
        
        # 4. Check if project is complete
        if kanban.get_stats()["completed"] == kanban.get_stats()["total_tasks"]:
            break
        
        # Sleep and check again
        time.sleep(10)
```

## 📊 Real-Time Updates

The dashboard sees all of this in real-time because:
1. I update `kanban.json` after every state change
2. Dashboard refreshes every 5 seconds
3. You see agents spawn, work, and complete live

## 🎯 End Result

After 6-12 hours overnight:
- ✅ All 25 tasks complete
- ✅ Full iOS app implemented
- ✅ All tests passing
- ✅ QA verified
- ✅ Ready for TestFlight

You wake up to a complete project! 🚀
