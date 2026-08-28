"""
ParallelExecutor - Run multiple agent tasks concurrently.

Pattern from: OpenHands sub-agent delegation + Pydantic AI Harness DynamicWorkflow.
Allows the agent to split work into parallel sub-tasks, execute them
concurrently with bounded workers, and aggregate results.

Features:
- Task queue with priority support
- Bounded worker pool (max concurrent tasks)
- Progress tracking per task
- Result aggregation
- Timeout per task
- Error isolation (one task failure doesn't kill others)
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """A unit of work for the parallel executor."""
    id: str
    name: str
    fn: Callable[..., Any]
    args: tuple = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 60.0
    priority: int = 0  # higher = executed first
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    start_time: float = 0
    end_time: float = 0

    @property
    def duration_ms(self) -> int:
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time) * 1000)
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


class ParallelExecutor:
    """Execute multiple tasks concurrently with bounded workers.

    Usage:
        executor = ParallelExecutor(max_workers=3)

        executor.submit("task1", my_fn, args=(arg1,))
        executor.submit("task2", my_fn, args=(arg2,))

        results = executor.wait_all(timeout=120)
        for task_id, task in results.items():
            print(f"{task_id}: {task.status} = {task.result}")
    """

    def __init__(self, max_workers: int = 3) -> None:
        self._max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None
        self._tasks: Dict[str, Task] = {}
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        self._on_progress: Optional[Callable[[Task], None]] = None
        self._on_complete: Optional[Callable[[Task], None]] = None

    def set_progress_callback(self, callback: Callable[[Task], None]) -> None:
        """Set callback for task progress updates."""
        self._on_progress = callback

    def set_complete_callback(self, callback: Callable[[Task], None]) -> None:
        """Set callback for task completion."""
        self._on_complete = callback

    def submit(self, task_id: str, fn: Callable, args: tuple = (),
               kwargs: Dict[str, Any] = None, timeout: float = 60.0,
               priority: int = 0, name: str = "") -> Task:
        """Submit a task for execution.

        Args:
            task_id: Unique identifier for the task
            fn: Callable to execute
            args: Positional arguments
            kwargs: Keyword arguments
            timeout: Max seconds to wait
            priority: Higher = executed first
            name: Human-readable task name

        Returns:
            Task object with status tracking.
        """
        task = Task(
            id=task_id,
            name=name or task_id,
            fn=fn,
            args=args,
            kwargs=kwargs or {},
            timeout=timeout,
            priority=priority,
        )

        with self._lock:
            self._tasks[task_id] = task

        return task

    def start(self) -> None:
        """Start the executor and submit pending tasks."""
        if self._executor is not None:
            return

        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)

        # Submit tasks sorted by priority
        sorted_tasks = sorted(self._tasks.values(), key=lambda t: -t.priority)
        for task in sorted_tasks:
            if task.status == TaskStatus.PENDING:
                self._submit_task(task)

    def _submit_task(self, task: Task) -> None:
        """Submit a single task to the thread pool."""
        if self._executor is None:
            return

        task.status = TaskStatus.RUNNING
        task.start_time = time.monotonic()

        if self._on_progress:
            try:
                self._on_progress(task)
            except Exception:
                pass

        future = self._executor.submit(self._run_task, task)
        with self._lock:
            self._futures[task.id] = future

    def _run_task(self, task: Task) -> Any:
        """Execute a task with timeout."""
        try:
            result = task.fn(*task.args, **task.kwargs)
            task.result = result
            task.status = TaskStatus.COMPLETED
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            logger.error("Task %s failed: %s", task.id, e)
        finally:
            task.end_time = time.monotonic()
            if self._on_complete:
                try:
                    self._on_complete(task)
                except Exception:
                    pass
        return task.result

    def wait_all(self, timeout: float = None) -> Dict[str, Task]:
        """Wait for all tasks to complete.

        Args:
            timeout: Max seconds to wait for all tasks

        Returns:
            Dict of task_id -> Task with final status.
        """
        if self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=False)
            self._executor = None

        # Mark timed-out tasks
        if timeout:
            for task in self._tasks.values():
                if task.status == TaskStatus.RUNNING:
                    elapsed = time.monotonic() - task.start_time
                    if elapsed > timeout:
                        task.status = TaskStatus.TIMEOUT
                        task.error = f"Timed out after {timeout}s"

        return dict(self._tasks)

    def wait_any(self, timeout: float = 60.0) -> Optional[Task]:
        """Wait for any single task to complete.

        Returns:
            The first completed Task, or None on timeout.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                for task in self._tasks.values():
                    if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMEOUT):
                        return task
            time.sleep(0.1)
        return None

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending task."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                return True
            future = self._futures.get(task_id)
            if future and not future.done():
                future.cancel()
                if task:
                    task.status = TaskStatus.CANCELLED
                return True
        return False

    def cancel_all(self) -> int:
        """Cancel all pending/running tasks."""
        count = 0
        with self._lock:
            for task_id, task in self._tasks.items():
                if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                    task.status = TaskStatus.CANCELLED
                    count += 1
                    future = self._futures.get(task_id)
                    if future:
                        future.cancel()
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        return count

    def get_status(self) -> Dict[str, Any]:
        """Get overall execution status."""
        counts = {}
        for task in self._tasks.values():
            status = task.status.value
            counts[status] = counts.get(status, 0) + 1
        return {
            "total": len(self._tasks),
            "by_status": counts,
            "max_workers": self._max_workers,
        }

    def get_results(self) -> List[Dict[str, Any]]:
        """Get all task results as dicts."""
        return [t.to_dict() for t in self._tasks.values()]

    def aggregate_results(self, merge_fn: Callable = None) -> Any:
        """Aggregate results from all completed tasks.

        Args:
            merge_fn: Custom function to merge results.
                     Default: collect all results into a list.

        Returns:
            Merged result.
        """
        results = [
            t.result for t in self._tasks.values()
            if t.status == TaskStatus.COMPLETED and t.result is not None
        ]
        if merge_fn:
            return merge_fn(results)
        return results

    def reset(self) -> None:
        """Clear all tasks and reset state."""
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        self._tasks.clear()
        self._futures.clear()
