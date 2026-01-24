"""
Ray Task System for Document Indexing - Dynamic Workflow Architecture

此模块实现了基于Ray的动态文档索引任务系统，取代原来Celery的工作流编排。
所有任务仍然使用结构化数据类进行参数和结果的传递。

## 架构核心

采用Ray remote函数实现并行与动态分发，主要特性如下:
1. **细粒度任务**：每个操作(parse, create, delete, update)单独Ray任务
2. **动态编排**：trigger/fan-out逻辑在Python函数中运行
3. **并行执行**：批量索引任务用Ray并发
4. **失败重试**：通过Python自管理重试(可扩展为Ray自带重试)
5. **运行时决策**：工作流根据解析结果灵活分发子任务

## 任务体系

- parse_document_task.remote(...)           解析文档
- create_index_task.remote(...)             创建单一索引
- delete_index_task.remote(...)             删除单一索引
- update_index_task.remote(...)             更新单一索引
- trigger_*_workflow                       动态分发
- notify_workflow_complete.remote(...)      聚合结果

## 工作流入口

- create_document_indexes_workflow(...)
- delete_document_indexes_workflow(...)
- update_document_indexes_workflow(...)

## 典型用法示例

```python
from config.celery_tasks import create_document_indexes_workflow

res_id = create_document_indexes_workflow(
    document_id="doc_123",
    index_types=["vector", "fulltext", "graph"]
)
# 获取最终结果
import ray
result = ray.get(res_id)
print(result)  # 结构同Celery中的 .to_dict()
```

## 动机&优点

- 真正原生并行，fan-out天然
- Python控制流可编写更灵活的调度
- 支持大规模分布式扩展
"""

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, List, Dict

import ray

from super_rag.tasks.document import document_index_task
from super_rag.models import (
    IndexTaskResult,
    ParsedDocumentData,
    TaskStatus,
    WorkflowResult,
)
from super_rag.db.models import DocumentIndexStatus
from super_rag.utils.constant import IndexAction

logger = logging.getLogger()

@ray.remote
def reconcile_indexes_task():
    """Periodic task to reconcile index specs with statuses"""
    try:
        logger.info("Starting index reconciliation")

        # Import here to avoid circular dependencies
        from super_rag.tasks.reconciler import index_reconciler

        # Run reconciliation
        index_reconciler.reconcile_all()

        logger.info("Index reconciliation completed")

    except Exception as e:
        logger.error(f"Index reconciliation failed: {e}", exc_info=True)
        raise


def _validate_task_relevance(document_id: str, index_type: str, target_version: int, expected_status: "DocumentIndexStatus"):
    from super_rag.db.models import DocumentIndex, DocumentIndexType, Document, DocumentStatus
    from super_rag.config import get_sync_session
    from sqlalchemy import select, and_

    for session in get_sync_session():
        stmt = select(DocumentIndex).where(
            and_(
                DocumentIndex.document_id == document_id,
                DocumentIndex.index_type == DocumentIndexType(index_type)
            )
        )
        result = session.execute(stmt)
        db_index = result.scalar_one_or_none()

        if not db_index:
            logger.info(f"Index record not found for {document_id}:{index_type}, skipping task.")
            return {"status": "skipped", "reason": "index_record_not_found"}

        if db_index.status != expected_status:
            logger.info(f"Index status for {document_id}:{index_type} changed to {db_index.status} (expected {expected_status}), skipping task.")
            return {"status": "skipped", "reason": f"status_changed_to_{db_index.status}"}

        if target_version and db_index.version != target_version:
            logger.info(f"Version mismatch for {document_id}:{index_type}, expected: {target_version}, current: {db_index.version}, skipping task.")
            return {"status": "skipped", "reason": f"version_mismatch_expected_{target_version}_current_{db_index.version}"}

        doc_stmt = select(Document).where(Document.id == document_id)
        doc_result = session.execute(doc_stmt)
        document = doc_result.scalar_one_or_none()

        if not document:
            logger.info(f"Document {document_id} not found, skipping task.")
            return {"status": "skipped", "reason": "document_not_found"}

        if document.status in [DocumentStatus.UPLOADED, DocumentStatus.EXPIRED]:
            logger.info(f"Document {document_id} status is {document.status}, skipping task.")
            return {"status": "skipped", "reason": f"document_status_{document.status}"}

        return None

class RayTaskCallbacksMixin:
    def _handle_index_success(self, document_id: str, index_type: str, target_version: int, index_data: dict = None):
        try:
            from super_rag.tasks.reconciler import index_task_callbacks
            index_data_json = json.dumps(index_data) if index_data else None
            index_task_callbacks.on_index_created(document_id, index_type, target_version, index_data_json)
            logger.info(f"Index success callback executed for {index_type} index of document {document_id} (v{target_version})")
        except Exception as e:
            logger.warning(f"Failed to execute index success callback for {index_type} of {document_id} v{target_version}: {e}", exc_info=True)

    def _handle_index_deletion_success(self, document_id: str, index_type: str):
        try:
            from super_rag.tasks.reconciler import index_task_callbacks
            index_task_callbacks.on_index_deleted(document_id, index_type)
            logger.info(f"Index deletion callback executed for {index_type} index of document {document_id}")
        except Exception as e:
            logger.warning(f"Failed to execute index deletion callback for {index_type} of {document_id}: {e}", exc_info=True)

    def _handle_index_failure(self, document_id: str, index_types: List[str], error_msg: str):
        try:
            from super_rag.tasks.reconciler import index_task_callbacks
            for index_type in index_types:
                index_task_callbacks.on_index_failed(document_id, index_type, error_msg)
            logger.info(f"Index failure callback executed for {index_types} indexes of document {document_id}")
        except Exception as e:
            logger.warning(f"Failed to execute index failure callback for {document_id}: {e}", exc_info=True)

raycallbacks = RayTaskCallbacksMixin()

@ray.remote
def parse_document_task(document_id: str, index_types: List[str]) -> dict:
    try:
        logger.info(f"Starting to parse document {document_id}")
        parsed_data = document_index_task.parse_document(document_id)
        logger.info(f"Successfully parsed document {document_id}")
        return parsed_data.to_dict()
    except Exception as e:
        error_msg = f"Failed to parse document {document_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raycallbacks._handle_index_failure(document_id, index_types, error_msg)
        raise

@ray.remote
def create_index_task(document_id: str, index_type: str, parsed_data_dict: dict, context: dict = None) -> dict:
    from super_rag.db.models import DocumentIndexStatus
    context = context or {}
    target_version = context.get(f'{index_type}_version')
    try:
        logger.info(f"Starting to create {index_type} index for document {document_id} (v{target_version})")

        skip_reason = _validate_task_relevance(document_id, index_type, target_version, DocumentIndexStatus.CREATING)
        if skip_reason:
            return skip_reason
        parsed_data = ParsedDocumentData.from_dict(parsed_data_dict)
        result = document_index_task.create_index(document_id, index_type, parsed_data)

        if not result.success:
            error_msg = f"Failed to create {index_type} index for document {document_id}: {result.error}"
            logger.error(error_msg)
            raise Exception(error_msg)

        logger.info(f"Successfully created {index_type} index for document {document_id} (v{target_version})")
        raycallbacks._handle_index_success(document_id, index_type, target_version, result.data)
        return result.to_dict()
    except Exception as e:
        error_msg = f"Failed to create {index_type} index for document {document_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raycallbacks._handle_index_failure(document_id, [index_type], error_msg)
        raise

@ray.remote
def delete_index_task(document_id: str, index_type: str) -> dict:
    from super_rag.db.models import DocumentIndex, DocumentIndexType, DocumentIndexStatus
    from super_rag.config import get_sync_session
    from sqlalchemy import select, and_

    try:
        logger.info(f"Starting to delete {index_type} index for document {document_id}")

        for session in get_sync_session():
            stmt = select(DocumentIndex).where(
                and_(
                    DocumentIndex.document_id == document_id,
                    DocumentIndex.index_type == DocumentIndexType(index_type)
                )
            )
            result = session.execute(stmt)
            db_index = result.scalar_one_or_none()
            if not db_index:
                logger.info(f"Index record not found for {document_id}:{index_type}, already deleted")
                return {"status": "skipped", "reason": "index_record_not_found"}
            if db_index.status != DocumentIndexStatus.DELETION_IN_PROGRESS:
                logger.info(f"Index status changed for {document_id}:{index_type}, current: {db_index.status}, skipping task")
                return {"status": "skipped", "reason": f"status_changed_to_{db_index.status}"}
            break

        result = document_index_task.delete_index(document_id, index_type)
        if not result.success:
            error_msg = f"Failed to delete {index_type} index for document {document_id}: {result.error}"
            logger.error(error_msg)
            raise Exception(error_msg)

        logger.info(f"Successfully deleted {index_type} index for document {document_id}")
        raycallbacks._handle_index_deletion_success(document_id, index_type)
        return result.to_dict()
    except Exception as e:
        error_msg = f"Failed to delete {index_type} index for document {document_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raycallbacks._handle_index_failure(document_id, [index_type], error_msg)
        raise

@ray.remote
def update_index_task(document_id: str, index_type: str, parsed_data_dict: dict, context: dict = None) -> dict:
    from super_rag.db.models import DocumentIndexStatus
    context = context or {}
    target_version = context.get(f'{index_type}_version')
    try:
        logger.info(f"Starting to update {index_type} index for document {document_id} (v{target_version})")
        skip_reason = _validate_task_relevance(document_id, index_type, target_version, DocumentIndexStatus.CREATING)
        if skip_reason:
            return skip_reason
        parsed_data = ParsedDocumentData.from_dict(parsed_data_dict)
        result = document_index_task.update_index(document_id, index_type, parsed_data)
        if not result.success:
            error_msg = f"Failed to update {index_type} index for document {document_id}: {result.error}"
            logger.error(error_msg)
            raise Exception(error_msg)
        logger.info(f"Successfully updated {index_type} index for document {document_id} (v{target_version})")
        raycallbacks._handle_index_success(document_id, index_type, target_version, result.data)
        return result.to_dict()
    except Exception as e:
        error_msg = f"Failed to update {index_type} index for document {document_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raycallbacks._handle_index_failure(document_id, [index_type], error_msg)
        raise

@ray.remote
def collection_delete_task(collection_id: str) -> dict:
    """
    Ray remote: Delete collection entry point.

    Args:
        collection_id: Collection ID to delete.
    """
    try:
        from super_rag.tasks.collection import collection_task
        result = collection_task.delete_collection(collection_id)

        if not result.success:
            raise Exception(result.error)

        logger.info(f"Collection {collection_id} deleted successfully")
        return result.to_dict()

    except Exception as e:
        logger.error(f"Collection deletion failed for {collection_id}: {str(e)}", exc_info=True)
        import traceback
        return {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


@ray.remote
def collection_init_task(collection_id: str) -> dict:
    """
    Ray remote: Initialize collection entry point.

    Args:
        collection_id: Collection ID to initialize
        document_user_quota: User quota for documents
    """
    try:
        from super_rag.tasks.collection import collection_task
        result = collection_task.initialize_collection(collection_id)

        if not result.success:
            raise Exception(result.error)

        logger.info(f"Collection {collection_id} initialized successfully")
        return result.to_dict()

    except Exception as e:
        logger.error(f"Collection initialization failed for {collection_id}: {str(e)}", exc_info=True)
        import traceback
        return {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


# ========== Workflow Entry Point Functions using Ray ==========

from typing import List, Optional

@ray.remote
def create_document_indexes_workflow(document_id: str, index_types: List[str], context: Optional[dict] = None) -> dict:
    """
    Create indexes for a document using Ray orchestration.

    This function:
    1. Parses the document
    2. Dynamically triggers parallel index creation based on parsed content
    3. Aggregates results and notifies completion

    Args:
        document_id: Document ID to process
        index_types: List of index types to create
        context: Optional context dictionary

    Returns:
        A dict indicating status/result of the workflow
    """
    logger.info(f"Starting create indexes workflow for document {document_id} with types: {index_types}")
    try:
        # Step 1: Parse the document
        parsed = ray.get(parse_document_task.remote(document_id, index_types))
        # Step 2: Dynamically trigger index creation (parallel for each index type)
        trigger_ref = trigger_create_indexes_workflow.remote(document_id, index_types, context, parsed)
        result = ray.get(trigger_ref)
        logger.info(f"Create indexes workflow completed for document {document_id}")
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        logger.error(f"Create indexes workflow failed for document {document_id}: {str(e)}", exc_info=True)
        import traceback
        return {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@ray.remote
def delete_document_indexes_workflow(document_id: str, index_types: List[str]) -> dict:
    """
    Delete indexes for a document using Ray orchestration.

    Args:
        document_id: Document ID to process
        index_types: List of index types to delete

    Returns:
        A dict indicating status/result of the workflow
    """
    logger.info(f"Starting delete indexes workflow for document {document_id} with types: {index_types}")
    try:
        # Directly trigger the delete workflow
        result = ray.get(trigger_delete_indexes_workflow.remote(document_id, index_types))
        logger.info(f"Delete indexes workflow completed for document {document_id}")
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        logger.error(f"Delete indexes workflow failed for document {document_id}: {str(e)}", exc_info=True)
        import traceback
        return {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@ray.remote
def update_document_indexes_workflow(document_id: str, index_types: List[str], context: Optional[dict] = None) -> dict:
    """
    Update indexes for a document using Ray orchestration.

    This function:
    1. Re-parses the document to get updated content
    2. Dynamically triggers parallel index updates based on parsed content
    3. Aggregates results and notifies completion

    Args:
        document_id: Document ID to process
        index_types: List of index types to update
        context: Optional context dictionary

    Returns:
        A dict indicating status/result of the workflow
    """
    logger.info(f"Starting update indexes workflow for document {document_id} with types: {index_types}")
    try:
        # Step 1: Parse (re-parse) the document
        parsed = ray.get(parse_document_task.remote(document_id, index_types))
        # Step 2: Dynamically trigger index updates (parallel for each index type)
        trigger_ref = trigger_update_indexes_workflow.remote(document_id, index_types, context, parsed)
        result = ray.get(trigger_ref)
        logger.info(f"Update indexes workflow completed for document {document_id}")
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        logger.error(f"Update indexes workflow failed for document {document_id}: {str(e)}", exc_info=True)
        import traceback
        return {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        }

# ========== Dynamic Workflow Orchestration Tasks (Ray implementation) ==========

@ray.remote
def trigger_create_indexes_workflow(document_id: str, index_types: List[str], context: dict = None, parsed_data_dict: dict = None) -> dict:
    """
    Dynamic orchestration task for index creation workflow, using Ray.

    Args:
        document_id: Document ID to process
        index_types: List of index types to create
        context: Optional context dictionary
        parsed_data_dict: Serialized ParsedDocumentData (if pre-parsed; can be None)

    Returns:
        Dict of aggregated create results.
    """
    try:
        logger.info(f"Triggering parallel index creation for document {document_id} with types: {index_types}")
        # If not provided, parse the document
        if parsed_data_dict is None:
            parsed_data_dict = ray.get(parse_document_task.remote(document_id, index_types))
        # Fan-out: launch multiple create_index_task in parallel by Ray
        create_refs = [
            create_index_task.remote(document_id, index_type, parsed_data_dict, context)
            for index_type in index_types
        ]
        # Wait for all tasks
        create_results = ray.get(create_refs)
        logger.info(f"Create indexes parallel tasks done for document {document_id}")
        # Completion notification/aggregation step
        workflow_result = notify_workflow_complete.remote(
            create_results, document_id, IndexAction.CREATE, index_types
        )
        result = ray.get(workflow_result)
        return result
    except Exception as e:
        error_msg = f"Failed to trigger create indexes workflow: {str(e)}"
        logger.error(error_msg, exc_info=True)
        import traceback
        return {
            "status": "failed",
            "error": error_msg,
            "traceback": traceback.format_exc()
        }

@ray.remote
def trigger_delete_indexes_workflow(document_id: str, index_types: List[str]) -> dict:
    """
    Dynamic orchestration task for index deletion workflow (Ray).

    Args:
        document_id: Document ID to process
        index_types: List of index types to delete

    Returns:
        Aggregated deletion results.
    """
    try:
        logger.info(f"Triggering parallel index deletion for document {document_id} with types: {index_types}")
        # Fan-out: multiple delete_index_task
        delete_refs = [
            delete_index_task.remote(document_id, index_type)
            for index_type in index_types
        ]
        delete_results = ray.get(delete_refs)
        logger.info(f"Delete indexes parallel tasks done for document {document_id}")
        # Completion aggregation
        workflow_result = notify_workflow_complete.remote(
            delete_results, document_id, IndexAction.DELETE, index_types
        )
        result = ray.get(workflow_result)
        return result
    except Exception as e:
        error_msg = f"Failed to trigger delete indexes workflow: {str(e)}"
        logger.error(error_msg, exc_info=True)
        import traceback
        return {
            "status": "failed",
            "error": error_msg,
            "traceback": traceback.format_exc()
        }

@ray.remote
def trigger_update_indexes_workflow(document_id: str, index_types: List[str], context: dict = None, parsed_data_dict: dict = None) -> dict:
    """
    Dynamic orchestration task for index update workflow (Ray).

    Args:
        document_id: Document ID to process
        index_types: List of index types to update
        context: Optional context
        parsed_data_dict: Parsed doc data, or None to re-parse.

    Returns:
        Aggregated update workflow results.
    """
    try:
        logger.info(f"Triggering parallel index update for document {document_id} with types: {index_types}")
        # If not provided, parse the document
        if parsed_data_dict is None:
            parsed_data_dict = ray.get(parse_document_task.remote(document_id, index_types))
        # Parallel update
        update_refs = [
            update_index_task.remote(document_id, index_type, parsed_data_dict, context)
            for index_type in index_types
        ]
        update_results = ray.get(update_refs)
        logger.info(f"Update indexes parallel tasks done for document {document_id}")
        workflow_result = notify_workflow_complete.remote(
            update_results, document_id, IndexAction.UPDATE, index_types
        )
        result = ray.get(workflow_result)
        return result
    except Exception as e:
        error_msg = f"Failed to trigger update indexes workflow: {str(e)}"
        logger.error(error_msg, exc_info=True)
        import traceback
        return {
            "status": "failed",
            "error": error_msg,
            "traceback": traceback.format_exc()
        }

@ray.remote
def notify_workflow_complete(index_results: List[dict], document_id: str, operation: str, index_types: List[str]) -> dict:
    """
    Workflow completion notification task (Ray variant).
    Aggregates results and provides final workflow status.

    Args:
        index_results: List of IndexTaskResult dicts from parallel tasks
        document_id: Document ID that was processed
        operation: Operation type ('create', 'delete', 'update')
        index_types: List of index types that were processed

    Returns:
        Serialized WorkflowResult as dict
    """
    try:
        logger.info(f"Workflow {operation} completed for document {document_id}")
        logger.info(f"Index results: {index_results}")

        successful_tasks = []
        failed_tasks = []
        for result_dict in index_results:
            try:
                result = IndexTaskResult.from_dict(result_dict)
                if getattr(result, "success", False):
                    successful_tasks.append(result.index_type)
                else:
                    failed_tasks.append(f"{result.index_type}: {getattr(result, 'error', 'unknown error')}")
            except Exception as e:
                failed_tasks.append(f"unknown: {str(e)}")
        # Determine overall status
        if not failed_tasks:
            status = TaskStatus.SUCCESS
            status_message = f"Document {document_id} {operation} COMPLETED SUCCESSFULLY! All indexes processed: {', '.join(successful_tasks)}"
            logger.info(status_message)
        elif successful_tasks:
            status = TaskStatus.PARTIAL_SUCCESS
            status_message = (
                f"Document {document_id} {operation} COMPLETED with WARNINGS. "
                f"Success: {', '.join(successful_tasks)}. "
                f"Failures: {'; '.join(failed_tasks)}"
            )
            logger.warning(status_message)
        else:
            status = TaskStatus.FAILED
            status_message = (
                f"Document {document_id} {operation} FAILED. All tasks failed: {'; '.join(failed_tasks)}"
            )
            logger.error(status_message)

        workflow_result = WorkflowResult(
            workflow_id=f"{document_id}_{operation}",
            document_id=document_id,
            operation=operation,
            status=status,
            message=status_message,
            successful_indexes=successful_tasks,
            failed_indexes=[f.split(":")[0] for f in failed_tasks],
            total_indexes=len(index_types),
            index_results=[IndexTaskResult.from_dict(r) for r in index_results],
        )
        return workflow_result.to_dict()
    except Exception as e:
        error_msg = f"Failed to process workflow completion for document {document_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        # Return failure result
        workflow_result = WorkflowResult(
            workflow_id=f"{document_id}_{operation}",
            document_id=document_id,
            operation=operation,
            status=TaskStatus.FAILED,
            message=error_msg,
            successful_indexes=[],
            failed_indexes=index_types,
            total_indexes=len(index_types),
            index_results=[],
        )
        return workflow_result.to_dict()



if __name__ == "__main__":
    reconcile_indexes_task.remote()