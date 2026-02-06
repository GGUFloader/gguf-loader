"""
Enterprise Agent - Full agentic loop implementation like Kiro
"""
import logging
from typing import Optional
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThread

from .loop_engine import AgenticLoop, AgentState
from .decision_engine import DecisionEngine
from .tool_executor import ToolExecutor
from .planner import TaskPlanner


class EnterpriseAgentWorker(QThread):
    """Worker thread for enterprise agent processing"""
    
    # Signals
    response_generated = Signal(str)
    status_update = Signal(str)
    error_occurred = Signal(str)
    processing_started = Signal()
    processing_finished = Signal()
    
    def __init__(self, agent, user_message: str):
        super().__init__()
        self.agent = agent
        self.user_message = user_message
        self._is_running = True
    
    def run(self):
        """Run agent processing in separate thread"""
        try:
            self.processing_started.emit()
            self.agent._process_message_internal(
                self.user_message,
                self.response_generated,
                self.status_update,
                self.error_occurred
            )
        except Exception as e:
            self.agent._logger.error(f"Worker thread error: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self.processing_finished.emit()
    
    def stop(self):
        """Stop the worker thread"""
        self._is_running = False


class EnterpriseAgent(QObject):
    """
    Enterprise-level agent with full agentic loop
    
    This agent works like Kiro:
    - Think → Act → Observe → Think again → Repeat
    - Multiple model calls per task
    - Adapts based on observations
    - Truly intelligent and dynamic
    """
    
    # Signals
    response_generated = Signal(str)
    status_update = Signal(str)
    error_occurred = Signal(str)
    processing_started = Signal()
    processing_finished = Signal()
    
    def __init__(self, model, workspace_path: str, max_iterations: int = 20):
        super().__init__()
        self.model = model
        self.workspace_path = Path(workspace_path)
        self.max_iterations = max_iterations
        self._logger = logging.getLogger(__name__)
        self._current_worker = None
        
        # Ensure workspace exists
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize planner
        self.planner = TaskPlanner(model, str(workspace_path))
        
        # Initialize components (decision engine will be created per-request with plan)
        self.tool_executor = ToolExecutor(str(workspace_path))
    
    def process_message(self, user_message: str):
        """Process user message asynchronously"""
        try:
            # Stop any existing worker
            if self._current_worker and self._current_worker.isRunning():
                self._current_worker.stop()
                self._current_worker.wait(1000)
            
            # Create and start new worker thread
            self._current_worker = EnterpriseAgentWorker(self, user_message)
            
            # Connect worker signals
            self._current_worker.response_generated.connect(self.response_generated.emit)
            self._current_worker.status_update.connect(self.status_update.emit)
            self._current_worker.error_occurred.connect(self.error_occurred.emit)
            self._current_worker.processing_started.connect(self.processing_started.emit)
            self._current_worker.processing_finished.connect(self.processing_finished.emit)
            
            # Start processing
            self._current_worker.start()
            
        except Exception as e:
            self._logger.error(f"Error starting agent worker: {e}")
            self.error_occurred.emit(str(e))
    
    def _process_message_internal(self, user_message: str, response_signal, status_signal, error_signal):
        """Internal message processing (runs in worker thread)"""
        try:
            # Store signals for callbacks
            self._response_signal = response_signal
            self._status_signal = status_signal
            self._error_signal = error_signal
            
            # Show initial message
            status_signal.emit(f"🎯 Goal: {user_message}")
            status_signal.emit("")
            
            # ============================================
            # STEP 1-3: PLANNING PHASE
            # ============================================
            status_signal.emit("📋 PLANNING PHASE")
            status_signal.emit("="*60)
            status_signal.emit("")
            
            try:
                # Create status callback for planner
                def planning_status(msg):
                    status_signal.emit(msg)
                
                # Create execution plan with streaming
                execution_plan = self.planner.create_plan(user_message, status_callback=planning_status)
                
                # Display the plan
                status_signal.emit("")
                status_signal.emit("✓ Plan created successfully!")
                status_signal.emit("")
                status_signal.emit(f"📊 Execution Plan:")
                status_signal.emit(f"   • Total tasks: {len(execution_plan.tasks)}")
                status_signal.emit(f"   • Estimated steps: {execution_plan.total_estimated_steps}")
                status_signal.emit("")
                
                for task in execution_plan.tasks:
                    status_signal.emit(f"   Task {task.id}: {task.description}")
                    status_signal.emit(f"      Type: {task.type.value}")
                    if task.required_tools:
                        status_signal.emit(f"      Tools: {', '.join(task.required_tools)}")
                    if task.dependencies:
                        status_signal.emit(f"      Depends on: Task {', '.join(map(str, task.dependencies))}")
                    status_signal.emit("")
                
            except Exception as e:
                error_msg = f"❌ ERROR in Planning Phase: {str(e)}"
                self._logger.error(error_msg)
                self._logger.error(f"Error type: {type(e).__name__}")
                self._logger.error(f"Error location: EnterpriseAgent._process_message_internal() - Planning")
                error_signal.emit(error_msg)
                error_signal.emit(f"Error type: {type(e).__name__}")
                error_signal.emit(f"Error location: Planning Phase")
                
                # Create simple fallback plan
                status_signal.emit("⚠️  Creating fallback plan...")
                from core.agent.planner import Task, ExecutionPlan, TaskType
                execution_plan = ExecutionPlan(
                    goal=user_message,
                    tasks=[Task(id=1, type=TaskType.ANALYZE, description=user_message, required_tools=[], dependencies=[], estimated_steps=3)],
                    total_estimated_steps=3,
                    execution_order=[1]
                )
            
            status_signal.emit("="*60)
            status_signal.emit("")
            
            # ============================================
            # EXECUTION PHASE: Task-by-Task Execution
            # ============================================
            status_signal.emit("⚡ EXECUTION PHASE (Task-by-Task Mode)")
            status_signal.emit("="*60)
            status_signal.emit("")
            
            try:
                status_signal.emit("Initializing decision engine...")
                
                # Create decision engine with the plan
                decision_engine = DecisionEngine(
                    self.model,
                    str(self.workspace_path),
                    execution_plan=execution_plan
                )
                
                status_signal.emit("Initializing loop engine...")
                
                # Create loop engine
                loop_engine = AgenticLoop(
                    decision_engine,
                    self.tool_executor,
                    max_iterations=self.max_iterations
                )
                
                status_signal.emit("Setting up callbacks...")
                
                # Set up callbacks
                loop_engine.set_callbacks(
                    on_think=self._on_think,
                    on_act=self._on_act,
                    on_observe=self._on_observe,
                    on_complete=self._on_complete,
                    on_status=lambda msg: status_signal.emit(msg),
                    on_user_update=lambda msg: status_signal.emit(f"💬 {msg}")
                )
                
                status_signal.emit("Starting task-by-task execution...")
                status_signal.emit("")
                
                # Run the agentic loop in TASK-BY-TASK mode
                final_state = loop_engine.run_task_by_task(user_message, execution_plan)
                
                # Generate final response
                if final_state.is_complete:
                    if final_state.final_answer:
                        response_signal.emit(final_state.final_answer)
                    else:
                        response_signal.emit("Task completed!")
                else:
                    response_signal.emit("Task incomplete - reached maximum iterations.")
                    
            except Exception as e:
                error_msg = f"❌ ERROR in Execution Phase: {str(e)}"
                self._logger.error(error_msg)
                self._logger.error(f"Error type: {type(e).__name__}")
                self._logger.error(f"Error location: EnterpriseAgent._process_message_internal() - Execution")
                error_signal.emit(error_msg)
                error_signal.emit(f"Error type: {type(e).__name__}")
                error_signal.emit(f"Error location: Execution Phase")
                
                # Try to provide partial results
                response_signal.emit("Task failed during execution. Check error messages above.")
            
        except Exception as e:
            error_msg = f"❌ CRITICAL ERROR: {str(e)}"
            self._logger.error(error_msg)
            self._logger.error(f"Error type: {type(e).__name__}")
            self._logger.error(f"Error location: EnterpriseAgent._process_message_internal() - Top Level")
            error_signal.emit(error_msg)
            error_signal.emit(f"Error type: {type(e).__name__}")
            error_signal.emit(f"Error location: Top Level")
            
            import traceback
            traceback_str = traceback.format_exc()
            self._logger.error(f"Full traceback:\n{traceback_str}")
            error_signal.emit(f"Full traceback:\n{traceback_str}")
    
    def _on_think(self, state: AgentState):
        """Called when agent is thinking"""
        iteration = state.iteration + 1
        self._status_signal.emit("")  # Blank line for separation
        self._status_signal.emit(f"{'='*60}")
        self._status_signal.emit(f"🧠 THINK (Step {iteration})")
        self._status_signal.emit(f"{'='*60}")
        self._status_signal.emit("Analyzing current state and deciding next action...")
    
    def _on_act(self, action):
        """Called when agent is acting"""
        self._status_signal.emit("")
        self._status_signal.emit(f"⚡ ACT")
        
        if action.reasoning:
            self._status_signal.emit(f"💭 {action.reasoning}")
        
        if action.tool:
            tool_desc = self._describe_tool_call(action.tool, action.parameters)
            self._status_signal.emit(f"🔧 {tool_desc}")
    
    def _on_observe(self, observation):
        """Called when agent observes result"""
        self._status_signal.emit("")
        self._status_signal.emit(f"👁️  OBSERVE")
        
        if observation.status == "success":
            self._status_signal.emit(f"✓ {observation.summary}")
        else:
            self._status_signal.emit(f"✗ {observation.summary}")
        
        self._status_signal.emit(f"{'='*60}")
    
    def _on_complete(self, state: AgentState):
        """Called when task is complete"""
        self._status_signal.emit("")
        self._status_signal.emit(f"{'='*60}")
        self._status_signal.emit(f"✅ COMPLETE - Task finished after {state.iteration} steps")
        self._status_signal.emit(f"{'='*60}")
        self._status_signal.emit("")
    
    def _describe_tool_call(self, tool_name: str, parameters: dict) -> str:
        """Generate human-readable description of tool call"""
        if tool_name == "write_file":
            path = parameters.get("path", "file")
            return f"Writing {path}"
        
        elif tool_name == "read_file":
            path = parameters.get("path", "file")
            return f"Reading {path}"
        
        elif tool_name == "list_directory":
            path = parameters.get("path", ".")
            return f"Listing files in {path}"
        
        elif tool_name == "edit_file":
            path = parameters.get("path", "file")
            return f"Editing {path}"
        
        elif tool_name == "search_files":
            pattern = parameters.get("pattern", "text")
            return f"Searching for '{pattern}'"
        
        else:
            return f"Executing {tool_name}"
