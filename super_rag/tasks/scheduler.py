import base64
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import ray
from ray.exceptions import TaskCancelledError

logger = logging.getLogger(__name__)

_RAY_TASK_SUPERVISOR_NAME = "super_rag_task_supervisor"
_RAY_TASK_SUPERVISOR_NAMESPACE = "super_rag"


class TaskResult:
    """Represents the result of a task execution"""

    def __init__(self, task_id: str, success: bool = True, error: str = None, data: Any = None):
        self.task_id = task_id
        self.success = success
        self.error = error
        self.data = data


class TaskScheduler(ABC):
    """Abstract base class for task schedulers"""

    @abstractmethod
    def schedule_create_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """
        Schedule single index creation task

        Args:
            document_id: Document ID to process
            index_types: List of index types (vector, fulltext, graph)
            context: Task context including version info
            **kwargs: Additional arguments

        Returns:
            Task ID for tracking
        """
        pass

    @abstractmethod
    def schedule_update_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """
        Schedule single index update task

        Args:
            document_id: Document ID to process
            index_types: List of index types (vector, fulltext, graph)
            context: Task context including version info
            **kwargs: Additional arguments

        Returns:
            Task ID for tracking
        """
        pass

    @abstractmethod
    def schedule_delete_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """
        Schedule single index deletion task

        Args:
            document_id: Document ID to process
            index_types: List of index types (vector, fulltext, graph)
            context: Task context including version info
            **kwargs: Additional arguments

        Returns:
            Task ID for tracking
        """
        pass

    @abstractmethod
    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """
        Get task execution status

        Args:
            task_id: Task ID to check

        Returns:
            TaskResult or None if task not found
        """
        pass

    @abstractmethod
    def cancel_task(self, task_id: str, force: bool = True, recursive: bool = True) -> bool:
        """
        Cancel a scheduled task.

        Args:
            task_id: Task ID returned by schedule_* methods
            force: Whether to force-kill a running task
            recursive: Whether to cancel child tasks recursively

        Returns:
            True if the cancellation request was accepted
        """
        pass


def create_task_scheduler(scheduler_type: str):
    if scheduler_type == "ray":
        return RayTaskScheduler()
    else:
        raise Exception("unknown task scheduler type: %s" % scheduler_type)


@ray.remote
class RayTaskSupervisor:
    """Detached actor that owns workflow ObjectRefs so they can be cancelled later."""

    def __init__(self):
        self._refs: Dict[str, ray.ObjectRef] = {}

    @staticmethod
    def _task_id_from_object_ref(obj_ref: ray.ObjectRef) -> str:
        return base64.urlsafe_b64encode(obj_ref.binary()).decode("ascii")

    def _track(self, obj_ref: ray.ObjectRef) -> str:
        task_id = self._task_id_from_object_ref(obj_ref)
        self._refs[task_id] = obj_ref
        return task_id

    def schedule_create_index(self, document_id: str, index_types: List[str], context: dict = None) -> str:
        from config.ray_tasks import create_document_indexes_workflow

        return self._track(create_document_indexes_workflow.remote(document_id, index_types, context))

    def schedule_update_index(self, document_id: str, index_types: List[str], context: dict = None) -> str:
        from config.ray_tasks import update_document_indexes_workflow

        return self._track(update_document_indexes_workflow.remote(document_id, index_types, context))

    def schedule_delete_index(self, document_id: str, index_types: List[str]) -> str:
        from config.ray_tasks import delete_document_indexes_workflow

        return self._track(delete_document_indexes_workflow.remote(document_id, index_types))

    def get_task_status(self, task_id: str) -> dict:
        obj_ref = self._refs.get(task_id)
        if obj_ref is None:
            return {"status": "missing", "error": "Task ref not found in supervisor"}

        ready_refs, _ = ray.wait([obj_ref], timeout=0)
        if not ready_refs:
            return {"status": "running"}

        try:
            result = ray.get(obj_ref)
        except TaskCancelledError as e:
            self._refs.pop(task_id, None)
            return {"status": "cancelled", "error": str(e)}
        except Exception as e:
            self._refs.pop(task_id, None)
            return {"status": "failed", "error": str(e)}

        self._refs.pop(task_id, None)
        return {"status": "finished", "result": result}

    def cancel_task(self, task_id: str, force: bool = True, recursive: bool = True) -> bool:
        obj_ref = self._refs.get(task_id)
        if obj_ref is None:
            logger.info(f"Ray task {task_id} is not tracked by supervisor; treating as already finished")
            return True

        ray.cancel(obj_ref, force=force, recursive=recursive)
        self._refs.pop(task_id, None)
        return True


class RayTaskScheduler(TaskScheduler):
    """Ray implementation of TaskScheduler - Direct workflow execution"""

    def __init__(self):
        self._supervisor = None

    @staticmethod
    def _get_or_create_supervisor():
        try:
            return ray.get_actor(_RAY_TASK_SUPERVISOR_NAME, namespace=_RAY_TASK_SUPERVISOR_NAMESPACE)
        except ValueError:
            try:
                return RayTaskSupervisor.options(
                    name=_RAY_TASK_SUPERVISOR_NAME,
                    namespace=_RAY_TASK_SUPERVISOR_NAMESPACE,
                    lifetime="detached",
                ).remote()
            except ValueError:
                return ray.get_actor(_RAY_TASK_SUPERVISOR_NAME, namespace=_RAY_TASK_SUPERVISOR_NAMESPACE)

    @property
    def supervisor(self):
        if self._supervisor is None:
            self._supervisor = self._get_or_create_supervisor()
        return self._supervisor

    def schedule_create_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """Schedule index creation workflow"""
        try:
            task_id = ray.get(self.supervisor.schedule_create_index.remote(document_id, index_types, context))
            logger.debug(f"Scheduled create indexes workflow {task_id} for document {document_id} with types {index_types}")
            return task_id
        except Exception as e:
            logger.error(f"Failed to schedule create indexes workflow for document {document_id}: {str(e)}")
            raise

    def schedule_update_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """Schedule index update workflow"""
        try:
            task_id = ray.get(self.supervisor.schedule_update_index.remote(document_id, index_types, context))
            logger.debug(f"Scheduled update indexes workflow {task_id} for document {document_id} with types {index_types}")
            return task_id
        except Exception as e:
            logger.error(f"Failed to schedule update indexes workflow for document {document_id}: {str(e)}")
            raise

    def schedule_delete_index(self, document_id: str, index_types: List[str], **kwargs) -> str:
        """Schedule index deletion workflow"""
        try:
            task_id = ray.get(self.supervisor.schedule_delete_index.remote(document_id, index_types))
            logger.debug(f"Scheduled delete indexes workflow {task_id} for document {document_id} with types {index_types}")
            return task_id
        except Exception as e:
            logger.error(f"Failed to schedule delete indexes workflow for document {document_id}: {str(e)}")
            raise

    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """Get workflow status using Ray ObjectRef (non-blocking)"""
        try:
            supervisor_result = ray.get(self.supervisor.get_task_status.remote(task_id))
            status = supervisor_result.get("status")

            if status == "running":
                return TaskResult(task_id, success=False, error="Task is pending or running")
            if status in {"missing", "failed", "cancelled"}:
                return TaskResult(task_id, success=False, error=str(supervisor_result.get("error")))

            # 我们的 Ray workflow 返回的是形如 {"status": "...", "error": "..."} 的 dict
            result = supervisor_result.get("result")
            if isinstance(result, dict):
                status = result.get("status")
                if status == "success":
                    return TaskResult(task_id, success=True, data=result)
                if status == "failed":
                    return TaskResult(task_id, success=False, error=str(result.get("error")), data=result)

            # 默认视为成功，直接返回数据
            return TaskResult(task_id, success=True, data=result)

        except TaskCancelledError as e:
            return TaskResult(task_id, success=False, error=str(e))
        except Exception as e:
            logger.error(f"Failed to get workflow status for {task_id}: {str(e)}")
            return TaskResult(task_id, success=False, error=str(e))

    def cancel_task(self, task_id: str, force: bool = True, recursive: bool = True) -> bool:
        """Cancel a Ray workflow through the supervisor that owns the ObjectRef."""
        try:
            ray.get(self.supervisor.cancel_task.remote(task_id, force, recursive))
            logger.info(f"Cancelled Ray task {task_id}")
            return True
        except TaskCancelledError:
            logger.info(f"Ray task {task_id} was already cancelled")
            return True
        except Exception as e:
            logger.warning(f"Failed to cancel Ray task {task_id}: {str(e)}")
            return False
