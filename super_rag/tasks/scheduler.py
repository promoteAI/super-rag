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
            # Execute workflow and return AsyncResult ID (not calling .get())
            workflow_result = ray.get(create_document_indexes_workflow.remote(document_id, index_types, context))  # Use .id instead of .get('workflow_id')
            logger.debug(
                f"Scheduled create indexes workflow {workflow_result} for document {document_id} with types {index_types}"
            )
        except Exception as e:
            logger.error(f"Failed to schedule create indexes workflow for document {document_id}: {str(e)}")
            raise

    def schedule_update_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """Schedule index update workflow"""
        from config.ray_tasks import update_document_indexes_workflow

        try:
            # Execute workflow and return AsyncResult ID (not calling .get())
            workflow_result = ray.get(update_document_indexes_workflow.remote(document_id, index_types, context))
            logger.debug(
                f"Scheduled update indexes workflow {workflow_result} for document {document_id} with types {index_types}"
            )
        except Exception as e:
            logger.error(f"Failed to schedule update indexes workflow for document {document_id}: {str(e)}")
            raise

    def schedule_delete_index(self, document_id: str, index_types: List[str], **kwargs) -> str:
        """Schedule index deletion workflow"""
        from config.ray_tasks import delete_document_indexes_workflow

        try:
            # Execute workflow and return AsyncResult ID
            workflow_result = ray.get(delete_document_indexes_workflow.remote(document_id, index_types))
            logger.debug(
                f"Scheduled delete indexes workflow {workflow_result} for document {document_id} with types {index_types}"
            )
        except Exception as e:
            logger.error(f"Failed to schedule delete indexes workflow for document {document_id}: {str(e)}")
            raise

    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """Get workflow status using Celery AsyncResult (non-blocking)"""
        try:
            from celery.result import AsyncResult

            from config.ray_schedule import app

            # Get AsyncResult without calling .get()
            workflow_result = AsyncResult(task_id, app=app)

            # Check status without blocking
            if workflow_result.state == "PENDING":
                return TaskResult(task_id, success=False, error="Workflow is pending")
            elif workflow_result.state == "STARTED":
                return TaskResult(task_id, success=False, error="Workflow is running")
            elif workflow_result.state == "SUCCESS":
                return TaskResult(task_id, success=True, data=workflow_result.result)
            elif workflow_result.state == "FAILURE":
                return TaskResult(task_id, success=False, error=str(workflow_result.info))
            else:
                return TaskResult(task_id, success=False, error=f"Unknown state: {workflow_result.state}")

        except Exception as e:
            logger.error(f"Failed to get workflow status for {task_id}: {str(e)}")
            return TaskResult(task_id, success=False, error=str(e))