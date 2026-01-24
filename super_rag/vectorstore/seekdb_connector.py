import pyseekdb
from pyseekdb import HNSWConfiguration
from typing import Any

from typing import List, Union
import logging
from pyseekdb import EmbeddingFunction
from super_rag.models import QueryWithEmbedding,QueryResult,DocumentWithScore

logger = logging.getLogger(__name__)

Documents = Union[str, List[str]]
Embeddings = List[List[float]]
Embedding = List[float]

class EmbeddingFunction(EmbeddingFunction[Documents]):
    """
    A custom embedding function using OpenAI's embedding API.
    """

    def __init__(self,dimension:int):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def __call__(self, input: Documents) -> Embeddings:
        pass

class SeekDBVectorStoreConnector:
    def __init__(self, ctx, **kwargs):
        self.ctx = ctx
        self.host = ctx.get("host", "localhost")
        self.port = ctx.get("port", 2881)
        self.timeout = ctx.get("timeout", 300)
        self.vector_size = ctx.get("vector_size", 1024)
        self.distance = ctx.get("distance", "cosine")
        self.collection_name = self.ctx["collection"]
        self.user = ctx.get("user", "root")
        self.password = ctx.get("password", "")
        self.database = ctx.get("database", "test")
        # Here, you would connect to SeekDB using context information.
        # For demonstration, we'll store nodes in an in-memory list.
        self.store = self
        self._nodes = []
        self.ef = EmbeddingFunction(self.vector_size)
        # 初始化
        self.client = pyseekdb.Client(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
        )
    def create_collection(self, **kwargs: Any):
        vector_size = kwargs.get("vector_size")
        configuration=HNSWConfiguration(
            dimension=vector_size, 
            distance=self.distance
        )
        self.client.create_collection(
            self.collection_name,
            configuration=configuration,
            embedding_function=self.ef,
            )

    def add(self, nodes):
        # Store nodes and return their IDs
        # 3. Generate embeddings for text chunks
        import uuid
        texts = [node.text for node in nodes]
        metadatas = [node.metadata for node in nodes]
        embeddings = [node.embedding for node in nodes]
        ids = [str(uuid.uuid4()) for _ in nodes]
        # 创造EMBEDDING函数
        collection=self.client.get_or_create_collection(self.collection_name)
        collection.add(ids,
                        embeddings=embeddings,
                        metadatas=metadatas,
                        documents=texts,
                        )
        print(f"\nAdded {len(texts)} documents to collection")
        print("Note: Embeddings were automatically generated from documents using the embedding function")
        return ids

    def delete_collection(self):
        self.client.delete_collection(self.collection_name)

    def search(self, query: QueryWithEmbedding, **kwargs):
        score_threshold = kwargs.get("score_threshold", 0.1)
        filter_conditions = kwargs.get("filter")

        collection=self.client.get_or_create_collection(self.collection_name)
        hits=collection.query(
            query_embeddings=query.embedding,
            query_texts=query.query,
            n_results=query.top_k,
        )
        logger.info(f"{hits}")

        results = self._convert_scored_point_to_document_with_score(hits)

        return QueryResult(
            query=query.query,
            results=results,
        )

    def _convert_scored_point_to_document_with_score(self, scored_points) -> list[DocumentWithScore] | None:
        """
        Convert SeekDB batch search output (with 'ids', 'distances', 'documents', 'metadatas')
        into a List[DocumentWithScore], using zip() for elegance.
        If it's not a batched result, degrade gracefully.
        """
        try:
            ids = scored_points.get("ids")
            distances = scored_points.get("distances")
            documents = scored_points.get("documents")
            metadatas = scored_points.get("metadatas")

            # Batched case: each field is a list-of-lists, e.g. [[id1, id2, id3]]
            if (
                isinstance(ids, list) and ids and isinstance(ids[0], list)
                and isinstance(distances, list) and distances and isinstance(distances[0], list)
                and isinstance(documents, list) and documents and isinstance(documents[0], list)
                and (metadatas is None or (isinstance(metadatas, list) and (not metadatas or isinstance(metadatas[0], list))))
            ):
                batch_ids = ids[0]
                batch_distances = distances[0]
                batch_documents = documents[0]
                batch_metadatas = metadatas[0] if metadatas else [None]*len(batch_ids)

                results = []
                for _id, dist, doc, meta in zip(batch_ids, batch_distances, batch_documents, batch_metadatas):
                    score = dist if dist is not None else None
                    results.append(
                        DocumentWithScore(
                            id=_id,
                            text=doc,
                            metadata=meta,
                            embedding=None,
                            score=score
                        )
                    )
                return results
        except Exception:
            logger.exception("Failed to convert scored point to document")
            return []