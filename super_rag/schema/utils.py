from gc import enable
import json
from typing import Any

from super_rag.schema.view_models import CollectionConfig, SharedCollectionConfig


def parseCollectionConfig(config: str) -> CollectionConfig:
    try:
        config_dict = json.loads(config)
        collection_config = CollectionConfig.model_validate(config_dict)
        return collection_config
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON string: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to parse collection config: {str(e)}")


def dumpCollectionConfig(collection_config: CollectionConfig) -> str:
    return collection_config.model_dump_json()


def convertToSharedCollectionConfig(config: CollectionConfig) -> SharedCollectionConfig:
    """Convert CollectionConfig to SharedCollectionConfig for marketplace display"""
    return SharedCollectionConfig(
        enable_vector_and_fulltext=config.enable_vector_and_fulltext if config.enable_vector_and_fulltext is not None else True,
        enable_knowledge_graph=config.enable_knowledge_graph if config.enable_knowledge_graph is not None else True,
        enable_summary=config.enable_summary if config.enable_summary is not None else False,
        enable_vision=config.enable_vision if config.enable_vision is not None else False,
    )


def normalize_schema_fields(data: Any) -> Any:
    """Recursively convert schema_ to schema for compatibility with old data.
    
    This function handles the case where old data was saved with 'schema_' field
    instead of 'schema' (the alias). It converts schema_ to schema so Pydantic
    models can properly validate the data.
    """
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key == 'schema_' and 'schema' not in result:
                # Convert schema_ to schema
                result['schema'] = normalize_schema_fields(value)
            else:
                result[key] = normalize_schema_fields(value)
        return result
    elif isinstance(data, list):
        return [normalize_schema_fields(item) for item in data]
    else:
        return data
