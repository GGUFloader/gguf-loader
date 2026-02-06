"""
Agent Orchestrator - Routes AI responses to appropriate handlers

This is the central coordinator that:
1. Sends prompts to AI
2. Parses AI's JSON response
3. Routes to appropriate handler (planner, tool executor, user updates)
4. Continues loop until complete
"""
import json
import re
import logging
from typing import Dict, Any, Optional, Callable
from pathlib import Path


class AgentOrchestrator:
    """
    Central orchestrator that manages the agent workflow
    
    Flow:
    1. User sends prompt
    2. AI generates planning JSON → Orchestrator sends to Planner
    3. Planner creates task list
    4. For each task:
       - AI generates tool call JSON → Orchestrator sends to Tool Executor
       - AI generates update JSON → Orchestrator sends to User
       - Tool executes and returns result
       - Loop continues
    5. When all tasks done, AI generates finish JSON
    """
    
    def __init__(self, model, workspace_path: str):
        """
        Initialize orchestrator
        
        Args:
            model: The AI model
            workspace_path: Path to workspace
        """
        self.model = model
        self.workspace_path = Path(workspace_path)
        self._logger = logging.getLogger(__name__)
        
        # Callbacks for routing
        self.on_planning = None      # Called with planning JSON
        self.on_tool_call = None     # Called with tool call JSON
        self.on_user_update = None   # Called with update message
        self.on_complete = None      # Called when finished
        
        # State
        self.task_list = []
        self.completed_tasks = []
        self.current_iteration = 0
    
    def process_user_prompt(self, user_prompt: str):
        """
        Process user prompt through the full workflow
        
        Args:
            user_prompt: The user's request
        """
        try:
            self._logger.info(f"Processing user prompt: {user_prompt}")
            
            # Step 1: Get planning from AI
            self._send_update("🔍 Analyzing your request...")
            planning_json = self._ask_ai_for_planning(user_prompt)
            
            # Step 2: Route planning to planner
            if self.on_planning:
                self.on_planning(planning_json)
            
            self.task_list = planning_json.get("tasks", [])
            self._send_update(f"📋 Created plan with {len(self.task_list)} tasks")
            
            # Show plan to user
            self._send_update("\n📊 Execution Plan:")
            for i, task in enumerate(self.task_list, 1):
                self._send_update(f"   {i}. {task.get('description', 'Task')}")
            self._send_update("")
            
            # Step 3: Execute tasks one by one
            self._send_update("⚡ Starting execution...\n")
            
            for task_id, task in enumerate(self.task_list, 1):
                self._execute_task(task_id, task, user_prompt)
            
            # Step 4: Finish
            self._send_update("\n✅ All tasks completed!")
            if self.on_complete:
                self.on_complete()
                
        except Exception as e:
            self._logger.error(f"Error in orchestrator: {e}")
            self._send_update(f"❌ Error: {str(e)}")
    
    def _execute_task(self, task_id: int, task: Dict, original_goal: str):
        """
        Execute a single task by asking AI for tool calls
        
        Args:
            task_id: Task number
            task: Task dictionary
            original_goal: Original user goal
        """
        try:
            self._send_update(f"{'='*60}")
            self._send_update(f"📌 Task {task_id}: {task.get('description')}")
            self._send_update(f"{'='*60}")
            
            # Keep asking AI for tool calls until task is complete
            max_steps = 10
            for step in range(max_steps):
                self.current_iteration += 1
                
                # Ask AI what to do next for this task
                self._send_update(f"\n🧠 THINK (Step {self.current_iteration})")
                
                response_json = self._ask_ai_for_action(task, original_goal)
                
                # Check if AI wants to finish this task
                if response_json.get("action") == "task_complete":
                    self._send_update(f"✓ Task {task_id} complete")
                    self.completed_tasks.append(task_id)
                    break
                
                # Extract update message for user
                if "update" in response_json:
                    self._send_update(f"💭 {response_json['update']}")
                
                # Extract tool call
                if "tool_call" in response_json:
                    tool_call = response_json["tool_call"]
                    self._send_update(f"⚡ ACT: {tool_call.get('tool')}")
                    
                    # Route to tool executor
                    if self.on_tool_call:
                        result = self.on_tool_call(tool_call)
                        self._send_update(f"👁️  OBSERVE: {result.get('summary', 'Done')}")
                
                # Check if we should continue
                if response_json.get("action") == "continue":
                    continue
                else:
                    break
            
            self._send_update("")
            
        except Exception as e:
            self._logger.error(f"Error executing task {task_id}: {e}")
            self._send_update(f"❌ Error in task {task_id}: {str(e)}")
    
    def _ask_ai_for_planning(self, user_prompt: str) -> Dict:
        """
        Ask AI to create a plan
        
        Args:
            user_prompt: User's request
            
        Returns:
            Planning JSON from AI
        """
        prompt = f"""You are a planning AI. Analyze the user's request and create a task plan.

User Request: {user_prompt}

Workspace: {self.workspace_path}

Respond with ONLY this JSON format:

```json
{{
    "analysis": "Brief analysis of what user wants",
    "tasks": [
        {{
            "id": 1,
            "description": "What this task does",
            "required_tools": ["tool1", "tool2"]
        }},
        {{
            "id": 2,
            "description": "Next task",
            "required_tools": ["tool3"]
        }}
    ]
}}
```

Available tools: list_directory, read_file, write_file, edit_file, search_files

Create the plan now:"""
        
        response = self._call_model(prompt)
        return self._extract_json(response)
    
    def _ask_ai_for_action(self, task: Dict, original_goal: str) -> Dict:
        """
        Ask AI what action to take for current task
        
        Args:
            task: Current task
            original_goal: Original user goal
            
        Returns:
            Action JSON from AI
        """
        prompt = f"""You are an action AI. Decide the next action for the current task.

Original Goal: {original_goal}
Current Task: {task.get('description')}
Required Tools: {task.get('required_tools', [])}

Workspace: {self.workspace_path}

Respond with ONLY this JSON format:

OPTION 1 - Call a tool:
```json
{{
    "action": "continue",
    "update": "Brief message to user about what you're doing",
    "tool_call": {{
        "tool": "tool_name",
        "parameters": {{"param": "value"}}
    }}
}}
```

OPTION 2 - Task is complete:
```json
{{
    "action": "task_complete",
    "update": "Task completed successfully"
}}
```

Available tools:
- list_directory: {{"path": "directory_path"}}
- read_file: {{"path": "file_path"}}
- write_file: {{"path": "file_path", "content": "content"}}
- edit_file: {{"path": "file_path", "operation": "replace", "find": "text", "replace": "text"}}
- search_files: {{"pattern": "search_text", "path": "directory_path"}}

Decide the next action:"""
        
        response = self._call_model(prompt)
        return self._extract_json(response)
    
    def _call_model(self, prompt: str) -> str:
        """Call AI model and get response"""
        try:
            from models.chat_generator import ChatGenerator
            
            chat_gen = ChatGenerator(
                model=self.model,
                prompt=prompt,
                chat_history=[],
                max_tokens=1024,
                temperature=0.1,
                system_prompt_name="assistant"
            )
            
            response_text = ""
            
            def on_token(token):
                nonlocal response_text
                response_text += token
            
            chat_gen.token_received.connect(on_token)
            chat_gen.run()
            
            return response_text
            
        except Exception as e:
            self._logger.error(f"Error calling model: {e}")
            raise
    
    def _extract_json(self, response: str) -> Dict:
        """Extract JSON from AI response"""
        try:
            # Try to find JSON in code blocks
            json_pattern = r'```json\s*(\{.*?\})\s*```'
            matches = re.findall(json_pattern, response, re.DOTALL)
            
            if not matches:
                # Try without code blocks
                matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            
            if not matches:
                raise ValueError("No JSON found in AI response")
            
            return json.loads(matches[0])
            
        except Exception as e:
            self._logger.error(f"Error extracting JSON: {e}")
            self._logger.error(f"Response was: {response[:500]}")
            raise
    
    def _send_update(self, message: str):
        """Send update to user"""
        if self.on_user_update:
            self.on_user_update(message)
        else:
            print(message)
    
    def set_callbacks(self, on_planning=None, on_tool_call=None, on_user_update=None, on_complete=None):
        """Set callback functions for routing"""
        self.on_planning = on_planning
        self.on_tool_call = on_tool_call
        self.on_user_update = on_user_update
        self.on_complete = on_complete
