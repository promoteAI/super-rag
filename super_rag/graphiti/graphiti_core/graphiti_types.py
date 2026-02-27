

from pydantic import BaseModel, ConfigDict

from super_rag.graphiti.graphiti_core.cross_encoder import CrossEncoderClient
from super_rag.graphiti.graphiti_core.driver.driver import GraphDriver
from super_rag.graphiti.graphiti_core.embedder import EmbedderClient
from super_rag.graphiti.graphiti_core.llm_client import LLMClient
from super_rag.graphiti.graphiti_core.tracer import Tracer


class GraphitiClients(BaseModel):
    driver: GraphDriver
    llm_client: LLMClient
    embedder: EmbedderClient
    cross_encoder: CrossEncoderClient
    tracer: Tracer

    model_config = ConfigDict(arbitrary_types_allowed=True)
