import logging
from abc import ABC, abstractmethod
from typing import Any, List, Optional
import ray

logger = logging.getLogger(__name__)


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


def create_task_scheduler(scheduler_type: str):
    if scheduler_type == "ray":
        return RayTaskScheduler()
    else:
        raise Exception("unknown task scheduler type: %s" % scheduler_type)


class RayTaskScheduler(TaskScheduler):
    """Celery implementation of TaskScheduler - Direct workflow execution"""

    def schedule_create_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """Schedule index creation workflow"""
        from config.ray_tasks import create_document_indexes_workflow

        try:
            # 异步触发 Ray workflow，返回 ObjectRef 的十六进制 ID 作为 task_id
            obj_ref = create_document_indexes_workflow.remote(document_id, index_types, context)
            logger.debug(
                f"Scheduled create indexes workflow {obj_ref} for document {document_id} with types {index_types}"
            )
            return obj_ref.hex()
        except Exception as e:
            logger.error(f"Failed to schedule create indexes workflow for document {document_id}: {str(e)}")
            raise

    def schedule_update_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """Schedule index update workflow"""
        from config.ray_tasks import update_document_indexes_workflow

        try:
            # 异步触发 Ray workflow，返回 ObjectRef 的十六进制 ID 作为 task_id
            obj_ref = update_document_indexes_workflow.remote(document_id, index_types, context)
            logger.debug(
                f"Scheduled update indexes workflow {obj_ref} for document {document_id} with types {index_types}"
            )
            return obj_ref.hex()
        except Exception as e:
            logger.error(f"Failed to schedule update indexes workflow for document {document_id}: {str(e)}")
            raise

    def schedule_delete_index(self, document_id: str, index_types: List[str], **kwargs) -> str:
        """Schedule index deletion workflow"""
        from config.ray_tasks import delete_document_indexes_workflow

        try:
            # 异步触发 Ray workflow，返回 ObjectRef 的十六进制 ID 作为 task_id
            obj_ref = delete_document_indexes_workflow.remote(document_id, index_types)
            logger.debug(
                f"Scheduled delete indexes workflow {obj_ref} for document {document_id} with types {index_types}"
            )
            return obj_ref.hex()
        except Exception as e:
            logger.error(f"Failed to schedule delete indexes workflow for document {document_id}: {str(e)}")
            raise

    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """Get workflow status using Ray ObjectRef (non-blocking)"""
        try:
            # 从十六进制字符串还原 Ray ObjectRef
            obj_ref = ray.ObjectRef.from_hex(task_id)

            # 非阻塞检查任务是否完成
            ready_refs, _ = ray.wait([obj_ref], timeout=0)
            if not ready_refs:
                return TaskResult(task_id, success=False, error="Task is pending or running")

            # 已完成，获取结果
            result = ray.get(obj_ref)

            # 我们的 Ray workflow 返回的是形如 {"status": "...", "error": "..."} 的 dict
            if isinstance(result, dict):
                status = result.get("status")
                if status == "success":
                    return TaskResult(task_id, success=True, data=result)
                if status == "failed":
                    return TaskResult(task_id, success=False, error=str(result.get("error")), data=result)

            # 默认视为成功，直接返回数据
            return TaskResult(task_id, success=True, data=result)

        except Exception as e:
            logger.error(f"Failed to get workflow status for {task_id}: {str(e)}")
            return TaskResult(task_id, success=False, error=str(e))