import logging
from typing import List
from super_rag.config import settings
from super_rag.fileparser.base import Part
from super_rag.chunk.chunking import rechunk
from super_rag.models import TextNode
from super_rag.utils.tokenizer import get_default_tokenizer
from super_rag.vectorstore.connector import VectorStoreConnectorAdaptor
from super_rag.llm import EmbeddingService

logger = logging.getLogger(__name__)

def create_embeddings_and_store(
    parts: List[Part],
    vector_store_adaptor: VectorStoreConnectorAdaptor,
    embedding_model:EmbeddingService,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
    tokenizer=None,
) -> List[str]:
    """
    Processes document parts, rechunks content, generates embeddings,
    and stores nodes in the vector database.

    Args:
        parts: List of document parts to process
        vector_store_adaptor: Vector store connector adaptor
        embedding_name: Embedding model to use for generating embeddings
        chunk_size: Size for chunking text (defaults to settings.chunk_size)
        chunk_overlap: Overlap size for chunking (defaults to settings.chunk_overlap_size)
        tokenizer: Tokenizer to use (defaults to default tokenizer)

    Returns:
        List[str]: A list of vector store IDs
    """
    if not parts:
        return []

    # Initialize parameters with defaults
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap_size
    tokenizer = tokenizer or get_default_tokenizer()

    nodes: List[TextNode] = []

    # 1. Rechunk the document parts (resulting in text parts)
    # After rechunk(), parts only contains TextPart
    chunked_parts = rechunk(parts, chunk_size, chunk_overlap, tokenizer)

    # 2. Process each text chunk
    for part in chunked_parts:
        if not part.content:
            continue

        # 2.1 Prepare metadata paddings (titles, labels)
        paddings = []
        # padding titles of the hierarchy
        if "titles" in part.metadata:
            paddings.append("> Hierarchy: " + " > ".join(part.metadata["titles"]))

        # padding user custom labels
        if "labels" in part.metadata:
            labels = []
            for item in part.metadata.get("labels", [{}]):
                if not item.get("key", None) or not item.get("value", None):
                    continue
                labels.append("%s=%s" % (item["key"], item["value"]))
            if labels:
                paddings.append("> Labels: " + " ".join(labels))

        prefix = ""
        if len(paddings) > 0:
            prefix = "\n".join(paddings)
            logger.debug("add extra prefix for document before embedding: %s", prefix)

        # 2.2 Construct text for embedding with paddings
        if prefix:
            text = f"{prefix}\n\n{part.content}"
        else:
            text = part.content
        # 2.3 Prepare metadata for the node
        metadata = part.metadata.copy()
        metadata["source"] = metadata.get("name", "")
        # 2.4 Create TextNode
        nodes.append(TextNode(text=text, metadata=metadata))

    # 3. Generate embeddings for text chunks
    texts = [node.text for node in nodes]
    vectors = embedding_model.embed_documents(texts)
    # 4. Assign embeddings to nodes
    for i in range(len(vectors)):
        nodes[i].embedding = vectors[i]
    logger.info(f"processed document with {len(parts)} parts and {len(nodes)} chunks")
    # 5. Add nodes to vector store and return results
    return vector_store_adaptor.connector.store.add(nodes)
