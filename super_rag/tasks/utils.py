from cgi import test
import json
from typing import Any, List, Tuple
from super_rag.exceptions import CollectionNotFoundException,DocumentNotFoundException

def parse_document_content(document, collection) -> Tuple[str, List[Any], Any]:
    """Parse document content for indexing (shared across all index types)"""
    from super_rag.index.document_parser import document_parser
    from super_rag.schema.utils import parseCollectionConfig
    # from super_rag.service.setting_service import setting_service
    from super_rag.source.base import get_source

    # Get document source and prepare local file

    source = get_source(parseCollectionConfig(collection.config))
    metadata = json.loads(document.doc_metadata or "{}")
    metadata["doc_id"] = document.id
    local_doc = source.prepare_document(name=document.name, metadata=metadata)

    try:
        # global_settings = setting_service.get_all_settings_sync()

        # Parse document to get content and parts
        parsing_result = document_parser.process_document_parsing(
            local_doc.path,
            local_doc.metadata,
            document.object_store_base_path(),
            # global_settings,
        )

        # Add chat metadata to all document parts if this is a chat upload
        doc_parts = parsing_result.doc_parts
        if document.doc_metadata:
            try:
                doc_metadata = json.loads(document.doc_metadata)
                if doc_metadata.get("file_type") == "chat_upload":
                    chat_id = doc_metadata.get("chat_id")
                    if chat_id:
                        for part in doc_parts:
                            if hasattr(part, "metadata"):
                                if part.metadata is None:
                                    part.metadata = {}
                                part.metadata["chat_id"] = chat_id
                                part.metadata["document_id"] = document.id
                            else:
                                # Create metadata if it doesn't exist
                                part.metadata = {"chat_id": chat_id, "document_id": document.id}
            except json.JSONDecodeError:
                pass

        return parsing_result.content, doc_parts, local_doc
    except Exception as e:
        # Cleanup on error
        source.cleanup_document(local_doc.path)
        raise e

def get_document_and_collection(document_id: str, ignore_deleted: bool = True):
    """Get document and collection objects"""
    from super_rag.db.ops import db_ops

    document = db_ops.query_document_by_id(document_id, ignore_deleted)
    if not document:
        raise DocumentNotFoundException(document_id)

    collection = db_ops.query_collection_by_id(document.collection_id, ignore_deleted)
    if not collection:
        raise CollectionNotFoundException(document.collection_id)

    return document, collection
