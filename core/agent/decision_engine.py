"""
Decision Engine - Makes intelligent decisions about what to do next
"""
import json
import re
import logging
from typing import Dict, Optional
from .loop_engine import Action, ActionType, AgentState


class DecisionEngine:
    """
    Makes decisions about what the agent should do next
    
    This is the "brain" of the agent - it calls the model to:
    1. Analyze the current state
    2. Decide what action to take next
    3. Determine if the task is complete
    """
    
    def __init__(self, model, workspace_path: str, execution_plan=None):
        """
        Initialize decision engine
        
        Args:
            model: The language model to use for decisions
            workspace_path: Path to the workspace
            execution_plan: Optional ExecutionPlan to guide decisions
        """
        self.model = model
        self.workspace_path = workspace_path
        self.execution_plan = execution_plan
        self._logger = logging.getLogger(__name__)
        
        # Task-by-task execution state
        self.current_task_id = None
        self.completed_task_ids = []
    
    def decide_next_action(self, state: AgentState, status_callback=None) -> Action:
        """
        Decide what action to take next based on current state
        
        Args:
            state: Current agent state
            status_callback: Optional callback for streaming status
            
        Returns:
            Action to take next
        """
        try:
            # Build prompt with current state
            if status_callback:
                status_callback("   📝 Building decision prompt...")
            self._logger.debug("Building decision prompt...")
            prompt = self._build_decision_prompt(state)
            
            # Call model
            if status_callback:
                status_callback("   🤖 Calling model for decision...")
            self._logger.debug("Calling model for decision...")
            response = self._call_model(prompt)
            
            if not response:
                raise Exception("Model returned empty response")
            
            # Show model response
            if status_callback:
                status_callback(f"   📄 Model response: {response[:200]}...")
            
            # Parse response into action
            if status_callback:
                status_callback("   🔍 Parsing model response...")
            self._logger.debug("Parsing model response into action...")
            action = self._parse_action(response)
            
            if status_callback:
                if action.type == ActionType.FINISH:
                    status_callback(f"   ⚠️  Model decided to FINISH: {action.reasoning}")
                else:
                    status_callback(f"   ✓ Model decided: {action.tool} with {action.parameters}")
            
            self._logger.debug(f"Decision made: {action.type.value}")
            return action
            
        except Exception as e:
            error_msg = f"Error in decide_next_action: {str(e)}"
            self._logger.error(error_msg)
            self._logger.error(f"Error type: {type(e).__name__}")
            self._logger.error(f"Error location: DecisionEngine.decide_next_action()")
            
            if status_callback:
                status_callback(f"   ❌ ERROR: {error_msg}")
            
            # Return finish action with error
            return Action(
                type=ActionType.FINISH,
                reasoning=f"Error making decision: {str(e)}"
            )
    
    def _build_decision_prompt(self, state: AgentState) -> str:
        """Build prompt for decision making"""
        prompt = f"""You are Kiro, an intelligent AI agent. You work in iterative steps:
Think → Act → Observe → Think again → Act → Repeat

Your goal: {state.goal}

Workspace: {self.workspace_path}

Available tools:
- list_directory: List files in a directory
  Parameters: {{"path": "directory_path"}}
  
- read_file: Read file contents
  Parameters: {{"path": "file_path"}}
  
- write_file: Create or overwrite files
  Parameters: {{"path": "file_path", "content": "file_content"}}
  
- edit_file: Modify existing files
  Parameters: {{"path": "file_path", "operation": "replace|insert_line|delete_line", "find": "text", "replace": "text", "line_number": 1, "content": "text"}}
  
- search_files: Search for text in files
  Parameters: {{"pattern": "search_text", "path": "directory_path"}}

"""
        
        # Add execution plan if available
        if self.execution_plan:
            prompt += "\n📋 YOUR EXECUTION PLAN (YOU MUST COMPLETE ALL TASKS):\n"
            prompt += f"Total tasks: {len(self.execution_plan.tasks)}\n"
            prompt += f"Estimated steps: {self.execution_plan.total_estimated_steps}\n\n"
            
            completed_count = 0
            for task in self.execution_plan.tasks:
                is_complete = self._is_task_complete(task, state)
                status = "✓ DONE" if is_complete else "○ TODO"
                if is_complete:
                    completed_count += 1
                
                prompt += f"{status} - Task {task.id}: {task.description}\n"
                
                if task.required_tools:
                    prompt += f"         Tools needed: {', '.join(task.required_tools)}\n"
                
                # CRITICAL: Show how many times tools need to be used
                if task.estimated_steps > 1:
                    prompt += f"         ⚠️  This task requires {task.estimated_steps} steps (not just 1!)\n"
                    
                    # Show progress for this specific task
                    if "read_file" in task.required_tools:
                        read_count = sum(1 for obs in state.observations if obs.action.tool == "read_file")
                        if read_count > 0:
                            prompt += f"         Progress: {read_count}/{task.estimated_steps} files read\n"
                
                if task.dependencies:
                    prompt += f"         Depends on: Task {', '.join(map(str, task.dependencies))}\n"
            
            prompt += f"\n⚠️  PROGRESS: {completed_count}/{len(self.execution_plan.tasks)} tasks complete\n"
            
            if completed_count < len(self.execution_plan.tasks):
                prompt += f"⚠️  YOU MUST CONTINUE - {len(self.execution_plan.tasks) - completed_count} tasks still TODO!\n"
            else:
                prompt += "✓ All tasks complete - you may finish now\n"
            
            prompt += "\n"
        
        # Add history if we have any
        if state.observations:
            prompt += f"\n📝 WHAT YOU'VE DONE SO FAR (Iteration {state.iteration}):\n{state.get_history_summary()}\n"
            
            # Show what data we have
            available_data = state.get_available_data()
            if available_data:
                prompt += "\n📦 DATA YOU'VE COLLECTED:\n"
                if "directory_listing" in available_data:
                    files = [item["name"] for item in available_data["directory_listing"] if item["type"] == "file"]
                    prompt += f"- Directory listing: {len(files)} files found\n"
                if "file_contents" in available_data:
                    prompt += f"- File contents: Read {len(available_data['file_contents'])} files\n"
                    for path in available_data["file_contents"].keys():
                        prompt += f"  • {path}\n"
        else:
            prompt += "\n📝 You haven't taken any actions yet. START NOW!\n"
        
        prompt += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOW DECIDE: What is your NEXT SINGLE action?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚨 BEFORE YOU DECIDE TO FINISH:
1. Look at the plan above - are ALL tasks marked "✓ DONE"?
2. If ANY task shows "○ TODO", you CANNOT finish yet!
3. Did you actually complete the user's goal, or just start it?
4. For "read files and create summary":
   - Did you list files? ✓
   - Did you read MULTIPLE files (not just one)? Check the progress counter!
   - Did you write the summary? ✓
5. If a task says "requires X steps", have you done ALL X steps?

⚠️  CRITICAL: Respond with EXACTLY ONE of these formats:

OPTION 1 - Call ONE tool:
```json
{
    "thinking": "Brief explanation of what I'm doing",
    "action": "tool_call",
    "tool": "tool_name",
    "parameters": {"param": "value"}
}
```

OPTION 2 - Finish (ONLY when ALL tasks complete):
```json
{
    "thinking": "All tasks are complete",
    "action": "finish",
    "reason_to_finish": "Summary of what was accomplished"
}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAMPLES OF CORRECT RESPONSES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Example 1 - List directory:
```json
{
    "thinking": "First I need to see what files are in the folder",
    "action": "tool_call",
    "tool": "list_directory",
    "parameters": {"path": "C:\\\\Users\\\\MY-PC\\\\Desktop\\\\New folder"}
}
```

Example 2 - Read a file:
```json
{
    "thinking": "Now I'll read the first file to understand its content",
    "action": "tool_call",
    "tool": "read_file",
    "parameters": {"path": "C:\\\\Users\\\\MY-PC\\\\Desktop\\\\New folder\\\\file1.txt"}
}
```

Example 3 - Write summary:
```json
{
    "thinking": "I've read all files, now I'll create the summary",
    "action": "tool_call",
    "tool": "write_file",
    "parameters": {
        "path": "C:\\\\Users\\\\MY-PC\\\\Desktop\\\\New folder\\\\summary.md",
        "content": "# Summary\\n\\n## File 1\\nContent about file 1...\\n\\n## File 2\\nContent about file 2..."
    }
}
```

Example 4 - Finish:
```json
{
    "thinking": "All tasks complete",
    "action": "finish",
    "reason_to_finish": "Successfully read 3 files and created summary.md with descriptions"
}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 CRITICAL RULES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ⚠️  ONE ACTION PER RESPONSE - This function will be called multiple times in a loop
2. ⚠️  DO NOT use arrays like "tool_calls": [...] - That's WRONG!
3. ⚠️  DO NOT call multiple tools at once - ONE tool at a time!
4. ⚠️  ONLY finish when ALL tasks in the plan show "✓ DONE"
5. ⚠️  If ANY task shows "○ TODO", you MUST continue with another tool_call

WRONG WORKFLOW (DON'T DO THIS):
❌ Step 1: List files → immediately finish (NO! You haven't read them!)
❌ Step 1: List files, Step 2: Read ONE file → finish (NO! Read ALL files!)
❌ Step 1-3: Do 3 actions → finish because "3 tasks done" (NO! Tasks ≠ Actions!)
❌ Try to do everything at once with multiple tools (NO! One at a time!)

CORRECT WORKFLOW (DO THIS):
✓ Step 1: List directory → observe results (Task 1 complete)
✓ Step 2: Read file 1 → observe content (Task 2 in progress: 1/5 files)
✓ Step 3: Read file 2 → observe content (Task 2 in progress: 2/5 files)
✓ Step 4: Read file 3 → observe content (Task 2 in progress: 3/5 files)
✓ Step 5: Read file 4 → observe content (Task 2 in progress: 4/5 files)
✓ Step 6: Read file 5 → observe content (Task 2 complete: 5/5 files)
✓ Step 7: Write summary.md with all content → observe success (Task 3 complete)
✓ Step 8: Check plan - all tasks ✓ DONE → NOW finish

REMEMBER: One TASK can require MULTIPLE STEPS!
- Task 2 "Read files" = 5 steps (read file 1, read file 2, read file 3, etc.)
- Don't confuse task count with step count!
- 3 tasks might need 7+ steps to complete!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REMEMBER: 
- Look at the plan above
- If it says "X/Y tasks complete" and X < Y, you MUST continue!
- Each response = ONE action
- You'll be called again after each action completes
"""
        
        return prompt
    
    def _call_model(self, prompt: str) -> str:
        """Call the model and get response"""
        try:
            from models.chat_generator import ChatGenerator
            
            self._logger.debug("Creating ChatGenerator...")
            
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
            
            self._logger.debug("Connecting token receiver...")
            chat_gen.token_received.connect(on_token)
            
            self._logger.debug("Running chat generator...")
            chat_gen.run()
            
            self._logger.debug(f"Model response length: {len(response_text)} chars")
            return response_text
            
        except Exception as e:
            error_msg = f"Error calling model in decision engine: {str(e)}"
            self._logger.error(error_msg)
            self._logger.error(f"Error type: {type(e).__name__}")
            self._logger.error(f"Error location: DecisionEngine._call_model()")
            
            import traceback
            traceback_str = traceback.format_exc()
            self._logger.error(f"Full traceback:\n{traceback_str}")
            
            raise Exception(error_msg) from e
    
    def _parse_action(self, response: str) -> Action:
        """Parse model response into an Action"""
        try:
            self._logger.debug("Parsing action from model response...")
            
            # Extract JSON from response
            json_pattern = r'```json\s*(\{.*?\})\s*```'
            matches = re.findall(json_pattern, response, re.DOTALL)
            
            if not matches:
                self._logger.warning("No JSON code block found, trying without code blocks...")
                # Try without code blocks - find the first complete JSON object
                json_objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
                if json_objects:
                    matches = [json_objects[0]]
            
            if not matches:
                self._logger.error("No JSON found in response")
                self._logger.error(f"Response was: {response[:500]}...")
                return Action(
                    type=ActionType.FINISH,
                    reasoning="ERROR: Model did not return valid JSON. Please check model configuration."
                )
            
            json_str = matches[0]
            self._logger.debug(f"Found JSON: {json_str[:200]}...")
            data = json.loads(json_str)
            
            # Check for wrong format: tool_calls array
            if "tool_calls" in data:
                self._logger.error("❌ MODEL USED WRONG FORMAT: tool_calls array")
                self._logger.error("Model is trying to call multiple tools at once!")
                self._logger.error(f"Wrong response: {json_str[:300]}...")
                
                # Try to extract first tool
                tool_calls = data.get("tool_calls", [])
                if tool_calls and len(tool_calls) > 0:
                    first_call = tool_calls[0]
                    self._logger.warning(f"Extracting FIRST tool only: {first_call.get('tool')}")
                    return Action(
                        type=ActionType.TOOL_CALL,
                        tool=first_call.get("tool"),
                        parameters=first_call.get("parameters", {}),
                        reasoning=data.get("reasoning", "Model used wrong format - extracted first tool")
                    )
                else:
                    return Action(
                        type=ActionType.FINISH,
                        reasoning="ERROR: Model returned empty tool_calls array"
                    )
            
            # Check for wrong field name: "reasoning" instead of "thinking"
            if "reasoning" in data and "thinking" not in data:
                self._logger.warning("Model used 'reasoning' instead of 'thinking' - accepting it")
                data["thinking"] = data["reasoning"]
            
            # Parse action type (correct format)
            action_type_str = data.get("action", "").lower()
            thinking = data.get("thinking", "")
            
            if not action_type_str:
                self._logger.error("No 'action' field in response")
                self._logger.error(f"Response data: {data}")
                return Action(
                    type=ActionType.FINISH,
                    reasoning="ERROR: Model response missing 'action' field"
                )
            
            self._logger.debug(f"Action type: {action_type_str}, thinking: {thinking[:100]}...")
            
            if action_type_str == "finish":
                reason = data.get("reason_to_finish", thinking)
                self._logger.info(f"Model decided to FINISH: {reason}")
                return Action(
                    type=ActionType.FINISH,
                    reasoning=reason
                )
            
            elif action_type_str == "tool_call":
                tool = data.get("tool")
                parameters = data.get("parameters", {})
                
                if not tool:
                    self._logger.error("tool_call action but no 'tool' field specified")
                    self._logger.error(f"Response data: {data}")
                    return Action(
                        type=ActionType.FINISH,
                        reasoning="ERROR: tool_call action missing 'tool' field"
                    )
                
                self._logger.info(f"Model decided to call tool: {tool}")
                return Action(
                    type=ActionType.TOOL_CALL,
                    tool=tool,
                    parameters=parameters,
                    reasoning=thinking
                )
            
            else:
                self._logger.error(f"Unknown action type: {action_type_str}")
                self._logger.error(f"Response data: {data}")
                return Action(
                    type=ActionType.FINISH,
                    reasoning=f"ERROR: Unknown action type '{action_type_str}'"
                )
                
        except json.JSONDecodeError as e:
            error_msg = f"JSON parsing error: {str(e)}"
            self._logger.error(error_msg)
            self._logger.error(f"Failed to parse: {matches[0][:300] if matches else 'no matches'}...")
            self._logger.error(f"Full response: {response[:500]}...")
            return Action(
                type=ActionType.FINISH,
                reasoning=f"ERROR: Invalid JSON in model response - {str(e)}"
            )
            
        except Exception as e:
            error_msg = f"Error parsing action: {str(e)}"
            self._logger.error(error_msg)
            self._logger.error(f"Error type: {type(e).__name__}")
            
            import traceback
            self._logger.error(f"Traceback: {traceback.format_exc()}")
            
            return Action(
                type=ActionType.FINISH,
                reasoning=f"ERROR: Failed to parse model response - {str(e)}"
            )

    
    def _is_task_complete(self, task, state: AgentState) -> bool:
        """
        Check if a task from the plan is complete based on observations
        
        IMPORTANT: Don't mark tasks complete too early!
        - Just using tools once doesn't mean the task is done
        - Need to check if the actual goal was achieved
        """
        if not task.required_tools:
            return False
        
        # Get all tool calls
        used_tools = [obs.action.tool for obs in state.observations if obs.action.tool]
        
        # First check: Have we used all required tools?
        all_tools_used = all(tool in used_tools for tool in task.required_tools)
        
        if not all_tools_used:
            return False  # Definitely not complete if tools haven't been used
        
        # Second check: For read_file tasks, ensure we read MULTIPLE files (not just one)
        if "read_file" in task.required_tools:
            read_count = sum(1 for obs in state.observations if obs.action.tool == "read_file")
            
            # If task says "read files" (plural) or estimated_steps > 1, we need multiple reads
            if task.estimated_steps > 1 and read_count < task.estimated_steps:
                return False  # Need to read more files based on estimated steps
            
            # If we listed files first, we should read at least 2-3 files minimum
            if "list_directory" in task.required_tools and read_count < 2:
                return False  # Listed files but only read one? Not done yet!
        
        # Third check: For write_file tasks, ensure write succeeded
        if "write_file" in task.required_tools:
            write_successes = [
                obs for obs in state.observations 
                if obs.action.tool == "write_file" and obs.status == "success"
            ]
            if not write_successes:
                return False  # write_file was required but didn't succeed
        
        # If all checks pass, task is likely complete
        return True
    
    def decide_next_action_for_task(self, state: AgentState, current_task, status_callback=None) -> Action:
        """
        Decide next action for a SPECIFIC task (task-by-task mode)
        
        This is the new focused approach where model only sees ONE task at a time.
        
        Args:
            state: Current agent state
            current_task: The specific task to work on
            status_callback: Optional callback for streaming status
            
        Returns:
            Action to take next for this task
        """
        try:
            # Build focused prompt for THIS task only
            if status_callback:
                status_callback("   📝 Building task-focused prompt...")
            
            prompt = self._build_task_focused_prompt(state, current_task)
            
            # Call model
            if status_callback:
                status_callback("   🤖 Calling model for decision...")
            
            response = self._call_model(prompt)
            
            if not response:
                raise Exception("Model returned empty response")
            
            # Parse response (expecting tool_call + user_update format)
            if status_callback:
                status_callback("   🔍 Parsing model response...")
            
            action = self._parse_task_action(response)
            
            if status_callback:
                if action.type == ActionType.FINISH:
                    status_callback(f"   ✓ Task complete: {action.reasoning}")
                else:
                    status_callback(f"   ✓ Next action: {action.tool}")
                    if action.reasoning:
                        status_callback(f"   💬 Update: {action.reasoning}")
            
            return action
            
        except Exception as e:
            self._logger.error(f"Error in decide_next_action_for_task: {str(e)}")
            
            if status_callback:
                status_callback(f"   ❌ ERROR: {str(e)}")
            
            return Action(
                type=ActionType.FINISH,
                reasoning=f"Error making decision: {str(e)}"
            )
    
    def _build_task_focused_prompt(self, state: AgentState, current_task) -> str:
        """Build prompt focused on ONLY the current task"""
        
        prompt = f"""You are Kiro, an intelligent AI agent working on a specific task.

OVERALL GOAL: {state.goal}

Workspace: {self.workspace_path}

Available tools:
- list_directory: List files in a directory
  Parameters: {{"path": "directory_path"}}
  
- read_file: Read file contents
  Parameters: {{"path": "file_path"}}
  
- write_file: Create or overwrite files
  Parameters: {{"path": "file_path", "content": "file_content"}}
  
- edit_file: Modify existing files
  Parameters: {{"path": "file_path", "operation": "replace|insert_line|delete_line", "find": "text", "replace": "text", "line_number": 1, "content": "text"}}
  
- search_files: Search for text in files
  Parameters: {{"pattern": "search_text", "path": "directory_path"}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 YOUR CURRENT TASK (Focus ONLY on this):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Task {current_task.id}: {current_task.description}
Type: {current_task.type.value}
Required tools: {', '.join(current_task.required_tools)}
Estimated steps: {current_task.estimated_steps}

"""
        
        # Show progress on THIS task
        task_observations = [obs for obs in state.observations 
                           if obs.action.tool in current_task.required_tools]
        
        if task_observations:
            prompt += "📝 PROGRESS ON THIS TASK:\n"
            for i, obs in enumerate(task_observations, 1):
                status_icon = "✓" if obs.status == "success" else "✗"
                prompt += f"   {i}. {status_icon} {obs.action.tool}: {obs.summary}\n"
            
            # Show specific progress counters
            if "read_file" in current_task.required_tools:
                read_count = len([o for o in task_observations if o.action.tool == "read_file"])
                prompt += f"\n   Files read: {read_count}/{current_task.estimated_steps}\n"
                
                if read_count < current_task.estimated_steps:
                    prompt += f"   ⚠️  Need to read {current_task.estimated_steps - read_count} more files!\n"
                else:
                    prompt += f"   ✓ All files read!\n"
            
            prompt += "\n"
        else:
            prompt += "📝 No actions taken for this task yet. Start now!\n\n"
        
        prompt += """━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DECIDE YOUR NEXT ACTION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Respond with JSON containing TWO things:

1. tool_call: The tool to execute
2. user_update: A message to show the user

OPTION 1 - Execute a tool:
```json
{
    "tool_call": {
        "tool": "tool_name",
        "parameters": {"param": "value"}
    },
    "user_update": "Brief message about what you're doing"
}
```

OPTION 2 - Task is complete:
```json
{
    "task_complete": true,
    "user_update": "Summary of what was accomplished"
}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAMPLES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Example 1 - List directory:
```json
{
    "tool_call": {
        "tool": "list_directory",
        "parameters": {"path": "."}
    },
    "user_update": "Listing files to see what's available"
}
```

Example 2 - Read file:
```json
{
    "tool_call": {
        "tool": "read_file",
        "parameters": {"path": "file1.py"}
    },
    "user_update": "Reading file1.py to understand its content"
}
```

Example 3 - Task complete:
```json
{
    "task_complete": true,
    "user_update": "Successfully read all 5 files"
}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ⚠️  Focus ONLY on the current task above
2. ⚠️  Do ONE action at a time
3. ⚠️  Always provide user_update to keep user informed
4. ⚠️  Check progress counter - if "2/5 files read", you need 3 more!
5. ⚠️  Only mark task_complete when ALL steps are done

Now decide your next action:
"""
        
        return prompt
    
    def _parse_task_action(self, response: str) -> Action:
        """Parse model response in task-focused format (tool_call + user_update)"""
        try:
            import json
            import re
            
            # Extract JSON
            json_pattern = r'```json\s*(\{.*?\})\s*```'
            matches = re.findall(json_pattern, response, re.DOTALL)
            
            if not matches:
                # Try without code blocks
                matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            
            if not matches:
                self._logger.error("No JSON found in response")
                return Action(
                    type=ActionType.FINISH,
                    reasoning="ERROR: Model did not return valid JSON"
                )
            
            data = json.loads(matches[0])
            
            # Check if task is complete
            if data.get("task_complete"):
                user_update = data.get("user_update", "Task complete")
                return Action(
                    type=ActionType.FINISH,
                    reasoning=user_update
                )
            
            # Extract tool call
            tool_call = data.get("tool_call", {})
            user_update = data.get("user_update", "")
            
            if not tool_call or "tool" not in tool_call:
                self._logger.error("No tool_call in response")
                return Action(
                    type=ActionType.FINISH,
                    reasoning="ERROR: No tool_call specified"
                )
            
            return Action(
                type=ActionType.TOOL_CALL,
                tool=tool_call.get("tool"),
                parameters=tool_call.get("parameters", {}),
                reasoning=user_update  # User update message
            )
            
        except Exception as e:
            self._logger.error(f"Error parsing task action: {str(e)}")
            return Action(
                type=ActionType.FINISH,
                reasoning=f"ERROR: Failed to parse response - {str(e)}"
            )
