
import logging
from datetime import datetime,timezone
import hashlib

logger = logging.getLogger(__name__)


AVAILABLE_SOURCE = ["system", "local", "s3"]

def generate_fulltext_index_name(collection_id) -> str:
    return str(collection_id)

def generate_vector_db_collection_name(collection_id) -> str:
    return str(collection_id)

def utc_now():
    return datetime.now(timezone.utc)

def calculate_file_hash(file_content: bytes) -> str:
    """
    Calculate SHA-256 hash of original file content for duplicate detection.

    Args:
        file_content: Original file content as bytes (raw file data)

    Returns:
        Hexadecimal string of SHA-256 hash
    """
    return hashlib.sha256(file_content).hexdigest()
