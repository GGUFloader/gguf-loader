"""
Task Planner - Analyzes user input and creates execution plan

This implements a 3-step planning process:
1. Task Analysis: Break down user input into discrete tasks
2. Tool Selection: Identify which tools are needed for each task
3. Scheduling: Determine the order and dependencies of tool calls
"""
import json
import re
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class TaskType(Enum):
    """Types of tasks the agent can identify"""
    READ = "read"           # Reading/analyzing files
    WRITE = "write"         # Creating new files
    EDIT = "edit"           # Modifying existing files
    SEARCH = "search"       # Searching for content
    ANALYZE = "analyze"     # Understanding/summarizing
    ORGANIZE = "organize"   # Moving/renaming files


@dataclass
class Task:
    """Represents a single task identified from user input"""
    id: int
    type: TaskType
    description: str
    required_tools: List[str] = field(default_factory=list)
    dependencies: List[int] = field(default_factory=list)  # IDs of tasks that must complete first
    estimated_steps: int = 1


@dataclass
class ExecutionPlan:
    """Complete execution plan for user request"""
    goal: str
    tasks: List[Task]
    total_estimated_steps: int
    execution_order: List[int]  # Task IDs in execution order
    
    def get_task(self, task_id: int) -> Optional[Task]:
        """Get task by ID"""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def get_next_task(self, completed_task_ids: List[int]) -> Optional[Task]:
        """Get next task that can be executed"""
        for task_id in self.execution_order:
            if task_id in completed_task_ids:
                continue
            
            task = self.get_task(task_id)
            if not task:
                continue
            
            # Check if all dependencies are met
            if all(dep_id in completed_task_ids for dep_id in task.dependencies):
                return task
        
        return None


class TaskPlanner:
    """
    Analyzes user input and creates execution plan
    
    This is the planning phase that happens BEFORE the Think-Act-Observe loop.
    It helps the agent understand the full scope of work upfront.
    """
    
    def __init__(self, model, workspace_path: str):
        """
        Initialize task planner
        
        Args:
            model: The language model to use for planning
            workspace_path: Path to the workspace
        """
        self.model = model
        self.workspace_path = workspace_path
        self._logger = logging.getLogger(__name__)
    
    def create_plan(self, user_input: str, status_callback=None) -> ExecutionPlan:
        """
        Create execution plan from user input
        
        This implements the 3-step process:
        1. Analyze tasks in the input
        2. Identify required tools
        3. Schedule execution order
        
        Args:
            user_input: The user's request
            status_callback: Optional callback for streaming status updates
            
        Returns:
            ExecutionPlan with tasks, tools, and schedule
        """
        try:
            if status_callback:
                status_callback("🔍 Step 1/3: Analyzing tasks in user input...")
            self._logger.info("Creating execution plan...")
            
            # Build planning prompt
            if status_callback:
                status_callback("   Building planning prompt...")
            prompt = self._build_planning_prompt(user_input)
            
            # Call model for planning
            if status_callback:
                status_callback("🔍 Step 2/3: Identifying required tools...")
                status_callback("   Calling model for analysis...")
            response = self._call_model(prompt)
            
            if not response:
                raise Exception("Model returned empty response during planning")
            
            # Parse response into plan
            if status_callback:
                status_callback("🔍 Step 3/3: Creating execution schedule...")
                status_callback("   Parsing model response...")
            plan = self._parse_plan(user_input, response)
            
            if status_callback:
                status_callback(f"✓ Plan created: {len(plan.tasks)} tasks, {plan.total_estimated_steps} estimated steps")
            self._logger.info(f"Plan created: {len(plan.tasks)} tasks, {plan.total_estimated_steps} estimated steps")
            
            return plan
            
        except Exception as e:
            error_msg = f"❌ ERROR in create_plan: {str(e)}"
            self._logger.error(error_msg)
            if status_callback:
                status_callback(error_msg)
                status_callback(f"   Error type: {type(e).__name__}")
                status_callback(f"   Error location: TaskPlanner.create_plan()")
            raise
    
    def _build_planning_prompt(self, user_input: str) -> str:
        """Build prompt for planning phase"""
        prompt = f"""You are Kiro's planning system. Your job is to analyze a user request and create an execution plan.

User Request: {user_input}

Workspace: {self.workspace_path}

Available Tools:
- list_directory: List files in a directory
- read_file: Read file contents
- write_file: Create or overwrite files
- edit_file: Modify existing files
- search_files: Search for text in files

Your task: Break down the user request into a structured plan with 3 steps:

STEP 1: TASK ANALYSIS
- How many distinct tasks are in this request?
- What is each task trying to accomplish?
- What type is each task (read, write, edit, search, analyze, organize)?

STEP 2: TOOL SELECTION
- Which tools are needed for each task?
- Are there any tools that will be used multiple times?

STEP 3: SCHEDULING
- What order should tasks be executed in?
- Which tasks depend on others completing first?
- Can any tasks be done in parallel (no dependencies)?

Respond with JSON in this format:
```json
{{
    "analysis": "Brief analysis of the request (1-2 sentences)",
    "tasks": [
        {{
            "id": 1,
            "type": "read|write|edit|search|analyze|organize",
            "description": "What this task does",
            "required_tools": ["tool1", "tool2"],
            "dependencies": [0],
            "estimated_steps": 2
        }}
    ],
    "execution_order": [1, 2, 3],
    "reasoning": "Why this order makes sense"
}}
```

CRITICAL PLANNING RULES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ⚠️  If user says "read files" or "read all files", you MUST create a task that uses read_file
2. ⚠️  If user wants a summary of files, you MUST:
   - Task 1: List directory (list_directory)
   - Task 2: Read MULTIPLE files (read_file) - mark estimated_steps as number of files to read
   - Task 3: Write summary (write_file)
3. ⚠️  Don't skip the reading step! If files need to be read, include read_file in required_tools
4. ⚠️  Be explicit about what needs to happen - don't assume the agent will figure it out

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXAMPLES:

Request: "Read all Python files and create a summary"
```json
{
    "analysis": "User wants to read Python files and create a summary document",
    "tasks": [
        {
            "id": 1,
            "type": "read",
            "description": "List directory to find all Python files",
            "required_tools": ["list_directory"],
            "dependencies": [],
            "estimated_steps": 1
        },
        {
            "id": 2,
            "type": "read",
            "description": "Read each Python file to understand content",
            "required_tools": ["read_file"],
            "dependencies": [1],
            "estimated_steps": 5
        },
        {
            "id": 3,
            "type": "write",
            "description": "Create summary.md with descriptions of all files",
            "required_tools": ["write_file"],
            "dependencies": [1, 2],
            "estimated_steps": 1
        }
    ],
    "execution_order": [1, 2, 3],
    "reasoning": "Must list files first, then read them, then write summary"
}
```

Request: "Create summary of files in folder"
```json
{
    "analysis": "User wants to read files and create a summary",
    "tasks": [
        {
            "id": 1,
            "type": "read",
            "description": "List all files in the folder",
            "required_tools": ["list_directory"],
            "dependencies": [],
            "estimated_steps": 1
        },
        {
            "id": 2,
            "type": "read",
            "description": "Read content of each file",
            "required_tools": ["read_file"],
            "dependencies": [1],
            "estimated_steps": 3
        },
        {
            "id": 3,
            "type": "write",
            "description": "Write summary.md with file descriptions",
            "required_tools": ["write_file"],
            "dependencies": [1, 2],
            "estimated_steps": 1
        }
    ],
    "execution_order": [1, 2, 3],
    "reasoning": "List files, read them, then create summary"
}
```

Request: "Find all TODO comments and create a task list"
```json
{
    "analysis": "User wants to search for TODO comments and compile them",
    "tasks": [
        {
            "id": 1,
            "type": "search",
            "description": "Search for TODO comments in all files",
            "required_tools": ["search_files"],
            "dependencies": [],
            "estimated_steps": 1
        },
        {
            "id": 2,
            "type": "write",
            "description": "Write task list file with all TODOs found",
            "required_tools": ["write_file"],
            "dependencies": [1],
            "estimated_steps": 1
        }
    ],
    "execution_order": [1, 2],
    "reasoning": "Search first, then write results"
}
```

Request: "Create a new config.json file with default settings"
```json
{
    "analysis": "User wants to create a new configuration file",
    "tasks": [
        {
            "id": 1,
            "type": "write",
            "description": "Create config.json with default settings",
            "required_tools": ["write_file"],
            "dependencies": [],
            "estimated_steps": 1
        }
    ],
    "execution_order": [1],
    "reasoning": "Simple file creation, no dependencies"
}
```

Now analyze the user request and create the plan:
"""
        
        return prompt
    
    def _call_model(self, prompt: str) -> str:
        """Call the model and get response"""
        try:
            from models.chat_generator import ChatGenerator
            
            self._logger.debug("Calling model for planning...")
            
            chat_gen = ChatGenerator(
                model=self.model,
                prompt=prompt,
                chat_history=[],
                max_tokens=2048,
                temperature=0.1,
                system_prompt_name="assistant"
            )
            
            response_text = ""
            
            def on_token(token):
                nonlocal response_text
                response_text += token
            
            chat_gen.token_received.connect(on_token)
            chat_gen.run()
            
            self._logger.debug(f"Model response length: {len(response_text)} chars")
            return response_text
            
        except Exception as e:
            error_msg = f"Error calling model in planner: {str(e)}"
            self._logger.error(error_msg)
            self._logger.error(f"Error type: {type(e).__name__}")
            self._logger.error(f"Error location: TaskPlanner._call_model()")
            raise Exception(error_msg) from e
    
    def _parse_plan(self, user_input: str, response: str) -> ExecutionPlan:
        """Parse model response into ExecutionPlan"""
        try:
            self._logger.debug("Parsing plan from model response...")
            
            # Extract JSON from response
            json_pattern = r'```json\s*(\{.*?\})\s*```'
            matches = re.findall(json_pattern, response, re.DOTALL)
            
            if not matches:
                self._logger.warning("No JSON code block found, trying without code blocks...")
                # Try without code blocks
                matches = re.findall(r'\{.*?\}', response, re.DOTALL)
            
            if not matches:
                self._logger.warning("No JSON found in response, creating simple plan")
                self._logger.debug(f"Response was: {response[:500]}...")
                return self._create_simple_plan(user_input)
            
            self._logger.debug(f"Found JSON match: {matches[0][:200]}...")
            data = json.loads(matches[0])
            
            # Parse tasks
            tasks = []
            for task_data in data.get("tasks", []):
                task_type_str = task_data.get("type", "analyze")
                try:
                    task_type = TaskType(task_type_str)
                except ValueError:
                    self._logger.warning(f"Unknown task type '{task_type_str}', using ANALYZE")
                    task_type = TaskType.ANALYZE
                
                task = Task(
                    id=task_data.get("id", len(tasks) + 1),
                    type=task_type,
                    description=task_data.get("description", ""),
                    required_tools=task_data.get("required_tools", []),
                    dependencies=task_data.get("dependencies", []),
                    estimated_steps=task_data.get("estimated_steps", 1)
                )
                tasks.append(task)
                self._logger.debug(f"Parsed task {task.id}: {task.description}")
            
            # Calculate total steps
            total_steps = sum(task.estimated_steps for task in tasks)
            
            # Get execution order
            execution_order = data.get("execution_order", [task.id for task in tasks])
            
            self._logger.info(f"Successfully parsed plan with {len(tasks)} tasks")
            
            return ExecutionPlan(
                goal=user_input,
                tasks=tasks,
                total_estimated_steps=total_steps,
                execution_order=execution_order
            )
        
        except json.JSONDecodeError as e:
            error_msg = f"JSON parsing error: {str(e)}"
            self._logger.error(error_msg)
            self._logger.error(f"Error location: TaskPlanner._parse_plan() - JSON decode")
            self._logger.debug(f"Failed to parse: {matches[0] if matches else 'no matches'}")
            return self._create_simple_plan(user_input)
        
        except Exception as e:
            error_msg = f"Error parsing plan: {str(e)}"
            self._logger.error(error_msg)
            self._logger.error(f"Error type: {type(e).__name__}")
            self._logger.error(f"Error location: TaskPlanner._parse_plan()")
            return self._create_simple_plan(user_input)
    
    def _create_simple_plan(self, user_input: str) -> ExecutionPlan:
        """Create a simple fallback plan"""
        task = Task(
            id=1,
            type=TaskType.ANALYZE,
            description=user_input,
            required_tools=[],
            dependencies=[],
            estimated_steps=3
        )
        
        return ExecutionPlan(
            goal=user_input,
            tasks=[task],
            total_estimated_steps=3,
            execution_order=[1]
        )
