"""
Agentic Loop Engine - The core Think-Act-Observe loop
"""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class ActionType(Enum):
    """Types of actions the agent can take"""
    TOOL_CALL = "tool_call"
    FINISH = "finish"
    THINK = "think"


@dataclass
class Action:
    """Represents an action the agent wants to take"""
    type: ActionType
    tool: Optional[str] = None
    parameters: Optional[Dict] = None
    reasoning: Optional[str] = None


@dataclass
class Observation:
    """Represents the result of an action"""
    action: Action
    status: str  # "success" or "error"
    result: Any
    summary: str  # Human-readable summary


@dataclass
class AgentState:
    """Current state of the agent"""
    goal: str
    observations: List[Observation] = field(default_factory=list)
    iteration: int = 0
    is_complete: bool = False
    final_answer: Optional[str] = None
    
    def add_observation(self, obs: Observation):
        """Add an observation to state"""
        self.observations.append(obs)
        self.iteration += 1
    
    def get_history_summary(self) -> str:
        """Get a summary of what's happened so far"""
        if not self.observations:
            return "No actions taken yet."
        
        summary_lines = []
        for i, obs in enumerate(self.observations, 1):
            action_desc = f"{obs.action.tool}" if obs.action.tool else "thinking"
            status_icon = "✓" if obs.status == "success" else "✗"
            summary_lines.append(f"{i}. {status_icon} {action_desc}: {obs.summary}")
        
        return "\n".join(summary_lines)
    
    def get_available_data(self) -> Dict[str, Any]:
        """Get all data collected so far"""
        data = {}
        for obs in self.observations:
            if obs.status == "success" and obs.result:
                tool = obs.action.tool
                if tool == "list_directory":
                    data["directory_listing"] = obs.result
                elif tool == "read_file":
                    path = obs.action.parameters.get("path", "unknown")
                    if "file_contents" not in data:
                        data["file_contents"] = {}
                    data["file_contents"][path] = obs.result
        return data


class AgenticLoop:
    """
    The core agentic loop engine
    
    This implements the Think-Act-Observe cycle:
    1. Think: Decide what to do next based on current state
    2. Act: Execute the decided action
    3. Observe: Record the result and update state
    4. Repeat until task is complete
    """
    
    def __init__(self, decision_engine, tool_executor, max_iterations=20):
        """
        Initialize the loop engine
        
        Args:
            decision_engine: Makes decisions about what to do next
            tool_executor: Executes tools
            max_iterations: Maximum number of loop iterations
        """
        self.decision_engine = decision_engine
        self.tool_executor = tool_executor
        self.max_iterations = max_iterations
        self._logger = logging.getLogger(__name__)
        
        # Callbacks for UI updates
        self.on_think = None  # Called when agent is thinking
        self.on_act = None    # Called when agent is acting
        self.on_observe = None  # Called when agent observes result
        self.on_complete = None  # Called when task is complete
        self.on_status = None  # Called for status updates
        self.on_user_update = None  # Called with user update messages
        
        # Task-by-task execution state
        self.current_task = None
        self.completed_tasks = []
    
    def run(self, goal: str) -> AgentState:
        """
        Run the agentic loop until task is complete
        
        Args:
            goal: The user's goal/task
            
        Returns:
            Final agent state with all observations
        """
        # Initialize state
        state = AgentState(goal=goal)
        
        self._logger.info(f"Starting agentic loop for goal: {goal}")
        
        try:
            # Main loop
            for iteration in range(self.max_iterations):
                self._logger.debug(f"Loop iteration {iteration + 1}/{self.max_iterations}")
                
                try:
                    # THINK: Decide next action
                    if self.on_think:
                        self.on_think(state)
                    
                    self._logger.debug("Calling decision engine...")
                    action = self.decision_engine.decide_next_action(state, status_callback=self.on_status)
                    self._logger.debug(f"Action decided: {action.type.value}")
                    
                    # Check if we're done
                    if action.type == ActionType.FINISH:
                        if self.on_status:
                            self.on_status(f"🏁 Agent decided to finish: {action.reasoning}")
                        state.is_complete = True
                        state.final_answer = action.reasoning
                        if self.on_complete:
                            self.on_complete(state)
                        break
                    
                    # ACT: Execute the action
                    if self.on_act:
                        self.on_act(action)
                    
                    if self.on_status:
                        self.on_status(f"   ⚙️  Executing: {action.tool}")
                    self._logger.debug(f"Executing action: {action.tool if action.tool else 'thinking'}")
                    observation = self._execute_action(action)
                    self._logger.debug(f"Action result: {observation.status}")
                    
                    # OBSERVE: Update state
                    state.add_observation(observation)
                    
                    if self.on_observe:
                        self.on_observe(observation)
                    
                    # Safety check: prevent infinite loops
                    if iteration >= self.max_iterations - 1:
                        self._logger.warning(f"Reached max iterations ({self.max_iterations})")
                        if self.on_status:
                            self.on_status(f"⚠️  Reached max iterations ({self.max_iterations})")
                        state.is_complete = True
                        state.final_answer = "Reached maximum iterations. Task may be incomplete."
                        break
                        
                except Exception as e:
                    error_msg = f"❌ ERROR in loop iteration {iteration + 1}: {str(e)}"
                    self._logger.error(error_msg)
                    self._logger.error(f"Error type: {type(e).__name__}")
                    self._logger.error(f"Error location: AgenticLoop.run() - iteration {iteration + 1}")
                    
                    # Create error observation
                    error_observation = Observation(
                        action=Action(type=ActionType.THINK, reasoning="Error occurred"),
                        status="error",
                        result=None,
                        summary=f"Error in iteration {iteration + 1}: {str(e)}"
                    )
                    state.add_observation(error_observation)
                    
                    if self.on_observe:
                        self.on_observe(error_observation)
                    
                    # Continue to next iteration instead of crashing
                    continue
            
            self._logger.info(f"Loop completed after {state.iteration} iterations")
            return state
            
        except Exception as e:
            error_msg = f"❌ CRITICAL ERROR in agentic loop: {str(e)}"
            self._logger.error(error_msg)
            self._logger.error(f"Error type: {type(e).__name__}")
            self._logger.error(f"Error location: AgenticLoop.run() - Top Level")
            
            import traceback
            traceback_str = traceback.format_exc()
            self._logger.error(f"Full traceback:\n{traceback_str}")
            
            # Return state with error
            state.is_complete = True
            state.final_answer = f"Critical error: {str(e)}"
            return state
    
    def run_task_by_task(self, goal: str, execution_plan) -> AgentState:
        """
        Run tasks ONE AT A TIME - focused execution
        
        This is the new approach where:
        1. Model sees ONLY current task (not all tasks)
        2. Works on that task until complete
        3. Moves to next task
        4. Keeps history of all tasks
        
        Args:
            goal: The user's goal/task
            execution_plan: ExecutionPlan with all tasks
            
        Returns:
            Final agent state with all observations
        """
        # Initialize state
        state = AgentState(goal=goal)
        
        self._logger.info(f"Starting task-by-task execution for goal: {goal}")
        self._logger.info(f"Total tasks: {len(execution_plan.tasks)}")
        
        try:
            # Execute tasks one by one
            for task in execution_plan.tasks:
                self.current_task = task
                
                if self.on_status:
                    self.on_status(f"\n{'='*60}")
                    self.on_status(f"📌 Starting Task {task.id}: {task.description}")
                    self.on_status(f"{'='*60}\n")
                
                self._logger.info(f"Starting task {task.id}: {task.description}")
                
                # Work on this task until complete
                task_iterations = 0
                max_task_iterations = task.estimated_steps + 5  # Allow some extra steps
                
                while task_iterations < max_task_iterations:
                    task_iterations += 1
                    
                    try:
                        # THINK: Decide next action for THIS task
                        if self.on_think:
                            self.on_think(state)
                        
                        self._logger.debug(f"Task {task.id}, iteration {task_iterations}")
                        action = self.decision_engine.decide_next_action_for_task(
                            state, task, status_callback=self.on_status
                        )
                        
                        # Check if task is complete
                        if action.type == ActionType.FINISH:
                            if self.on_status:
                                self.on_status(f"✓ Task {task.id} complete: {action.reasoning}")
                            self.completed_tasks.append(task.id)
                            break
                        
                        # ACT: Execute the action
                        if self.on_act:
                            self.on_act(action)
                        
                        # Show user update if provided
                        if action.reasoning and self.on_user_update:
                            self.on_user_update(action.reasoning)
                        
                        if self.on_status:
                            self.on_status(f"   ⚙️  Executing: {action.tool}")
                        
                        observation = self._execute_action(action)
                        
                        # OBSERVE: Update state
                        state.add_observation(observation)
                        
                        if self.on_observe:
                            self.on_observe(observation)
                        
                    except Exception as e:
                        error_msg = f"❌ ERROR in task {task.id}, iteration {task_iterations}: {str(e)}"
                        self._logger.error(error_msg)
                        
                        error_observation = Observation(
                            action=Action(type=ActionType.THINK, reasoning="Error occurred"),
                            status="error",
                            result=None,
                            summary=f"Error: {str(e)}"
                        )
                        state.add_observation(error_observation)
                        
                        if self.on_observe:
                            self.on_observe(error_observation)
                        
                        continue
                
                if task_iterations >= max_task_iterations:
                    self._logger.warning(f"Task {task.id} reached max iterations")
                    if self.on_status:
                        self.on_status(f"⚠️  Task {task.id} reached max iterations, moving to next task")
                
                self._logger.info(f"Task {task.id} completed after {task_iterations} iterations")
            
            # All tasks complete
            state.is_complete = True
            state.final_answer = f"All {len(execution_plan.tasks)} tasks completed successfully!"
            
            if self.on_complete:
                self.on_complete(state)
            
            self._logger.info(f"All tasks completed after {state.iteration} total iterations")
            return state
            
        except Exception as e:
            error_msg = f"❌ CRITICAL ERROR in task-by-task execution: {str(e)}"
            self._logger.error(error_msg)
            
            import traceback
            self._logger.error(f"Full traceback:\n{traceback.format_exc()}")
            
            state.is_complete = True
            state.final_answer = f"Critical error: {str(e)}"
            return state
    
    def _execute_action(self, action: Action) -> Observation:
        """
        Execute an action and return observation
        
        Args:
            action: The action to execute
            
        Returns:
            Observation with the result
        """
        try:
            if action.type == ActionType.TOOL_CALL:
                self._logger.debug(f"Executing tool: {action.tool} with params: {action.parameters}")
                result = self.tool_executor.execute(action.tool, action.parameters)
                
                return Observation(
                    action=action,
                    status=result.get("status", "error"),
                    result=result.get("result"),
                    summary=result.get("summary", str(result))
                )
            
            elif action.type == ActionType.THINK:
                # Just thinking, no execution
                return Observation(
                    action=action,
                    status="success",
                    result=None,
                    summary=action.reasoning or "Thinking..."
                )
            
            else:
                error_msg = f"Unknown action type: {action.type}"
                self._logger.error(error_msg)
                return Observation(
                    action=action,
                    status="error",
                    result=None,
                    summary=error_msg
                )
        
        except Exception as e:
            error_msg = f"Error executing action: {str(e)}"
            self._logger.error(error_msg)
            self._logger.error(f"Error type: {type(e).__name__}")
            self._logger.error(f"Error location: AgenticLoop._execute_action()")
            self._logger.error(f"Action was: {action.type.value} - {action.tool}")
            
            return Observation(
                action=action,
                status="error",
                result=None,
                summary=f"Error: {str(e)}"
            )
    
    def set_callbacks(self, on_think=None, on_act=None, on_observe=None, on_complete=None, on_status=None, on_user_update=None):
        """Set callback functions for UI updates"""
        self.on_think = on_think
        self.on_act = on_act
        self.on_observe = on_observe
        self.on_complete = on_complete
        self.on_status = on_status
        self.on_user_update = on_user_update
