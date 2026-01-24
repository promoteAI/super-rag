from enum import Enum
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional,Literal
from pydantic import BaseModel

class TaskStatus(Enum):
    """Task execution status"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"
    PARTIAL_SUCCESS = "partial_success"

class DocumentIndexType(str, Enum):
    """Document index type enumeration"""

    VECTOR_AND_FULLTEXT= "VECTOR_AND_FULLTEXT"
    GRAPH = "GRAPH"
    SUMMARY = "SUMMARY"
    VISION = "VISION"

@dataclass
class IndexTaskResult:
    """Result of an index operation"""

    status: TaskStatus
    index_type: str
    document_id: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,  # Convert enum to string
            "index_type": self.index_type,
            "document_id": self.document_id,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IndexTaskResult":
        return cls(
            status=TaskStatus(data["status"]),
            index_type=data["index_type"],
            document_id=data["document_id"],
            success=data["success"],
            data=data.get("data"),
            error=data.get("error"),
            message=data.get("message"),
        )

    @classmethod
    def success_result(
        cls, index_type: str, document_id: str, data: Dict[str, Any] = None, message: str = None
    ) -> "IndexTaskResult":
        return cls(
            status=TaskStatus.SUCCESS,
            index_type=index_type,
            document_id=document_id,
            success=True,
            data=data,
            message=message,
        )

    @classmethod
    def failed_result(cls, index_type: str, document_id: str, error: str) -> "IndexTaskResult":
        return cls(status=TaskStatus.FAILED, index_type=index_type, document_id=document_id, success=False, error=error)

@dataclass
class LocalDocumentInfo:
    """Information about local document file"""

    path: str
    is_temp: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ParsedDocumentData:
    """Structured data from document parsing"""

    document_id: str
    collection_id: str
    content: str
    doc_parts: List[Any]
    file_path: str
    local_doc_info: LocalDocumentInfo

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict with proper serialization of doc_parts"""
        return {
            "document_id": self.document_id,
            "collection_id": self.collection_id,
            "content": self.content,
            "doc_parts": self._serialize_doc_parts(self.doc_parts),
            "file_path": self.file_path,
            "local_doc_info": self.local_doc_info.to_dict(),
        }

    def _serialize_doc_parts(self, doc_parts: List[Any]) -> List[Dict[str, Any]]:
        """Serialize doc_parts to JSON-compatible format"""
        serialized_parts = []
        for part in doc_parts:
            if hasattr(part, "to_dict"):
                # If the part has a to_dict method, use it
                serialized_parts.append(part.to_dict())
            elif hasattr(part, "model_dump"):
                # If the part has a model_dump() method (pydantic), use it
                serialized_parts.append(part.model_dump())
            elif hasattr(part, "__dict__"):
                # If it's an object with attributes, convert to dict
                part_dict = {}
                for key, value in part.__dict__.items():
                    if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                        part_dict[key] = value
                    else:
                        # Convert non-serializable objects to string representation
                        part_dict[key] = str(value)
                part_dict["_type"] = part.__class__.__name__
                serialized_parts.append(part_dict)
            else:
                # Fallback: convert to string
                serialized_parts.append({"content": str(part), "_type": part.__class__.__name__})
        return serialized_parts

    def _deserialize_doc_parts(self, serialized_parts: List[Dict[str, Any]]) -> List[Any]:
        """Deserialize doc_parts from JSON format"""
        # Create simple wrapper objects that mimic the original part behavior
        deserialized_parts = []
        for part_dict in serialized_parts:
            # Create a simple object with attributes from the dict
            part_obj = type("DocumentPart", (), part_dict)()
            deserialized_parts.append(part_obj)
        return deserialized_parts

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParsedDocumentData":
        local_doc_info = LocalDocumentInfo(**data["local_doc_info"])
        instance = cls(
            document_id=data["document_id"],
            collection_id=data["collection_id"],
            content=data["content"],
            doc_parts=[],  # Will be set below
            file_path=data["file_path"],
            local_doc_info=local_doc_info,
        )
        # Deserialize doc_parts to restore object-like behavior
        instance.doc_parts = instance._deserialize_doc_parts(data["doc_parts"])
        return instance

class TaskResult:
    """Standardized task result format"""

    def __init__(
        self, success: bool, data: Any = None, error: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None
    ):
        self.success = success
        self.data = data
        self.error = error
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {"success": self.success, "data": self.data, "error": self.error, "metadata": self.metadata}

@dataclass
class WorkflowResult:
    """Result of a workflow execution"""

    workflow_id: str
    document_id: str
    operation: str  # 'create', 'update', 'delete'
    status: TaskStatus
    message: str
    successful_indexes: List[str]
    failed_indexes: List[str]
    total_indexes: int
    index_results: List[IndexTaskResult]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "document_id": self.document_id,
            "operation": self.operation,
            "status": self.status.value,
            "message": self.message,
            "successful_indexes": self.successful_indexes,
            "failed_indexes": self.failed_indexes,
            "total_indexes": self.total_indexes,
            "index_results": [r.to_dict() for r in self.index_results],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowResult":
        return cls(
            workflow_id=data["workflow_id"],
            document_id=data["document_id"],
            operation=data["operation"],
            status=TaskStatus(data["status"]),
            message=data["message"],
            successful_indexes=data["successful_indexes"],
            failed_indexes=data["failed_indexes"],
            total_indexes=data["total_indexes"],
            index_results=[IndexTaskResult.from_dict(r) for r in data["index_results"]],
        )

    @property
    def all_successful(self) -> bool:
        return len(self.failed_indexes) == 0

    @property
    def has_partial_success(self) -> bool:
        return len(self.successful_indexes) > 0 and len(self.failed_indexes) > 0

class TextNode:
    """
    代表文本节点的数据结构。

    Attributes:
        text (str): 节点的文本内容。
        metadata (Dict[str, Any]): 节点相关的元数据信息。
        embedding (Optional[List[float]]): 节点的嵌入向量。
    """
    def __init__(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[list] = None
    ):
        self.text = text
        self.metadata = metadata or {}
        self.embedding = embedding

    def to_dict(self) -> Dict[str, Any]:
        """将TextNode对象序列化为字典。"""
        return {
            "text": self.text,
            "metadata": self.metadata,
            "embedding": self.embedding
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextNode":
        """从字典反序列化为TextNode对象。"""
        return cls(
            text=data.get("text", ""),
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding")
        )

class APIType(str, Enum):
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    RERANK = "rerank"

class DocumentWithScore(BaseModel):
    text: Optional[str] = None
    score: Optional[float] = None
    metadata: Optional[dict] = None


class Reference(BaseModel):
    score: Optional[float] = None
    text: Optional[str] = None
    image_uri: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class Feedback(BaseModel):
    type: Optional[Literal['good', 'bad']] = None
    tag: Optional[Literal['Harmful', 'Unsafe', 'Fake', 'Unhelpful', 'Other']] = None
    message: Optional[str] = None


class File(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class ChatMessage(BaseModel):
    id: Optional[str] = None
    part_id: Optional[str] = None
    type: Optional[
        Literal[
            'welcome',
            'message',
            'start',
            'stop',
            'error',
            'tool_call_result',
            'thinking',
            'references',
        ]
    ] = None
    timestamp: Optional[float] = None
    role: Optional[Literal['human', 'ai']] = None
    data: Optional[str] = None
    references: Optional[list[Reference]] = None
    urls: Optional[list[str]] = None
    feedback: Optional[Feedback] = None
    files: Optional[list[File]] = None

class Query(BaseModel):
    query: str
    top_k: Optional[int] = 3

class QueryWithEmbedding(Query):
    embedding: List[float]

class QueryResult(BaseModel):
    query: str
    results: List[DocumentWithScore]

