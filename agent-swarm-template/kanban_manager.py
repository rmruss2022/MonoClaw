#!/usr/bin/env python3
"""
Kanban Manager for Agent Swarm Orchestration
Manages kanban.json state for project tracking
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional

class KanbanManager:
    def __init__(self, project_dir: str):
        """Initialize kanban manager for a project directory."""
        self.project_dir = project_dir
        self.kanban_file = os.path.join(project_dir, 'kanban.json')
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Load kanban.json from disk."""
        if not os.path.exists(self.kanban_file):
            return self._create_empty()
        
        with open(self.kanban_file, 'r') as f:
            return json.load(f)
    
    def _save(self):
        """Save kanban.json to disk."""
        with open(self.kanban_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def _create_empty(self) -> Dict:
        """Create empty kanban structure."""
        return {
            "project": {
                "name": os.path.basename(self.project_dir),
                "description": "",
                "reference": "",
                "created_at": datetime.now().isoformat(),
                "status": "not-started",
                "target_completion": None
            },
            "stats": {
                "total_tasks": 0,
                "completed": 0,
                "in_progress": 0,
                "ready": 0,
                "qa": 0,
                "blocked": 0,
                "estimated_hours_remaining": 0
            },
            "tasks": [],
            "agents": {
                "active": [],
                "completed": []
            },
            "activity_log": []
        }
    
    def set_project_info(self, name: str, description: str = "", reference: str = ""):
        """Update project information."""
        self.data["project"]["name"] = name
        self.data["project"]["description"] = description
        self.data["project"]["reference"] = reference
        self._save()
    
    def add_task(self, 
                 title: str,
                 description: str = "",
                 priority: str = "medium",
                 estimated_hours: float = 1.0,
                 dependencies: List[str] = None,
                 tags: List[str] = None) -> str:
        """Add a new task to the kanban board."""
        task_id = f"task-{len(self.data['tasks']) + 1}"
        
        task = {
            "id": task_id,
            "title": title,
            "description": description,
            "state": "todo",
            "assigned_to": None,
            "agent_session_key": None,
            "started_at": None,
            "completed_at": None,
            "spec_file": None,
            "code_files": [],
            "dependencies": dependencies or [],
            "priority": priority,
            "estimated_hours": estimated_hours,
            "actual_hours": 0,
            "tags": tags or []
        }
        
        self.data["tasks"].append(task)
        self._update_stats()
        self._log_activity("system", None, f"Task created: {title}", "info")
        self._save()
        return task_id
    
    def update_task_state(self, task_id: str, new_state: str, message: str = ""):
        """Update task state (todo|in-progress|ready|qa|complete|blocked)."""
        task = self._find_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        old_state = task["state"]
        task["state"] = new_state
        
        if new_state == "in-progress" and not task["started_at"]:
            task["started_at"] = datetime.now().isoformat()
        elif new_state == "complete" and not task["completed_at"]:
            task["completed_at"] = datetime.now().isoformat()
        
        self._update_stats()
        self._log_activity("system", task_id, 
                          f"State changed: {old_state} → {new_state}" + 
                          (f" ({message})" if message else ""), "update")
        self._save()
    
    def assign_agent(self, task_id: str, agent_id: str, session_key: str):
        """Assign an agent to a task."""
        task = self._find_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        task["assigned_to"] = agent_id
        task["agent_session_key"] = session_key
        
        # Add to active agents
        self.data["agents"]["active"].append({
            "agent_id": agent_id,
            "session_key": session_key,
            "task_id": task_id,
            "spawned_at": datetime.now().isoformat(),
            "status": "running"
        })
        
        self._log_activity(agent_id, task_id, f"Agent assigned to task", "spawn")
        self._save()
    
    def agent_completed(self, agent_id: str, task_id: str, result: str):
        """Mark an agent as completed."""
        # Remove from active
        self.data["agents"]["active"] = [
            a for a in self.data["agents"]["active"] 
            if not (a["agent_id"] == agent_id and a["task_id"] == task_id)
        ]
        
        # Add to completed
        self.data["agents"]["completed"].append({
            "agent_id": agent_id,
            "task_id": task_id,
            "completed_at": datetime.now().isoformat(),
            "result": result
        })
        
        self._log_activity(agent_id, task_id, result, "completion")
        self._save()
    
    def get_ready_tasks(self) -> List[Dict]:
        """Get all tasks in 'ready' state with met dependencies."""
        ready_tasks = []
        completed_ids = {t["id"] for t in self.data["tasks"] if t["state"] == "complete"}
        
        for task in self.data["tasks"]:
            if task["state"] == "ready":
                deps_met = all(dep in completed_ids for dep in task["dependencies"])
                if deps_met:
                    ready_tasks.append(task)
        
        return ready_tasks
    
    def get_todo_tasks(self) -> List[Dict]:
        """Get all tasks in 'todo' state with met dependencies."""
        todo_tasks = []
        completed_ids = {t["id"] for t in self.data["tasks"] if t["state"] == "complete"}
        
        for task in self.data["tasks"]:
            if task["state"] == "todo":
                deps_met = all(dep in completed_ids for dep in task["dependencies"])
                if deps_met and not task["assigned_to"]:
                    todo_tasks.append(task)
        
        return todo_tasks
    
    def add_task_file(self, task_id: str, file_type: str, file_path: str):
        """Add a file reference to a task (spec_file or code_files)."""
        task = self._find_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        if file_type == "spec":
            task["spec_file"] = file_path
        elif file_type == "code":
            if file_path not in task["code_files"]:
                task["code_files"].append(file_path)
        
        self._save()
    
    def _find_task(self, task_id: str) -> Optional[Dict]:
        """Find a task by ID."""
        for task in self.data["tasks"]:
            if task["id"] == task_id:
                return task
        return None
    
    def _update_stats(self):
        """Recalculate project statistics."""
        tasks = self.data["tasks"]
        self.data["stats"] = {
            "total_tasks": len(tasks),
            "completed": sum(1 for t in tasks if t["state"] == "complete"),
            "in_progress": sum(1 for t in tasks if t["state"] == "in-progress"),
            "ready": sum(1 for t in tasks if t["state"] == "ready"),
            "qa": sum(1 for t in tasks if t["state"] == "qa"),
            "blocked": sum(1 for t in tasks if t["state"] == "blocked"),
            "estimated_hours_remaining": sum(
                t["estimated_hours"] - t["actual_hours"] 
                for t in tasks if t["state"] != "complete"
            )
        }
    
    def _log_activity(self, agent: str, task_id: Optional[str], message: str, type: str):
        """Add an entry to the activity log."""
        self.data["activity_log"].append({
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "task_id": task_id,
            "message": message,
            "type": type
        })
        
        # Keep only last 100 entries
        if len(self.data["activity_log"]) > 100:
            self.data["activity_log"] = self.data["activity_log"][-100:]
    
    def get_stats(self) -> Dict:
        """Get current project statistics."""
        return self.data["stats"]
    
    def get_all_tasks(self) -> List[Dict]:
        """Get all tasks."""
        return self.data["tasks"]
    
    def get_active_agents(self) -> List[Dict]:
        """Get all active agents."""
        return self.data["agents"]["active"]


# Example usage
if __name__ == "__main__":
    # Create a test project
    import tempfile
    
    project_dir = tempfile.mkdtemp()
    kanban = KanbanManager(project_dir)
    
    # Set project info
    kanban.set_project_info(
        "iOS Banking App",
        "Agent swarm building an iOS app similar to o-p-e-n.com",
        "https://o-p-e-n.com/everywhere"
    )
    
    # Add some tasks
    task1 = kanban.add_task(
        "User Authentication",
        "Implement login/register/password reset flows",
        priority="high",
        estimated_hours=4,
        tags=["auth", "ios", "ui"]
    )
    
    task2 = kanban.add_task(
        "Payment Integration",
        "Integrate Stripe payment processing",
        priority="high",
        estimated_hours=6,
        dependencies=[task1],
        tags=["payments", "backend"]
    )
    
    # Simulate workflow
    kanban.update_task_state(task1, "in-progress")
    kanban.assign_agent(task1, "ios-dev-1", "agent:dev:subagent:abc123")
    kanban.add_task_file(task1, "spec", "specs/auth.md")
    kanban.update_task_state(task1, "qa")
    kanban.agent_completed(task1, "ios-dev-1", "Authentication UI complete")
    kanban.update_task_state(task1, "complete")
    
    # Print stats
    print(json.dumps(kanban.get_stats(), indent=2))
    print(f"\nKanban file created at: {kanban.kanban_file}")
