

import json
from typing import Any

from super_rag.graphiti.graphiti_core.driver.record_parsers import entity_edge_from_record, entity_node_from_record
from super_rag.graphiti.graphiti_core.edges import EntityEdge
from super_rag.graphiti.graphiti_core.nodes import EntityNode


def parse_kuzu_entity_node(record: Any) -> EntityNode:
    """Parse a Kuzu entity node record, deserializing JSON attributes."""
    if isinstance(record.get('attributes'), str):
        try:
            record['attributes'] = json.loads(record['attributes'])
        except (json.JSONDecodeError, TypeError):
            record['attributes'] = {}
    elif record.get('attributes') is None:
        record['attributes'] = {}
    return entity_node_from_record(record)


def parse_kuzu_entity_edge(record: Any) -> EntityEdge:
    """Parse a Kuzu entity edge record, deserializing JSON attributes."""
    if isinstance(record.get('attributes'), str):
        try:
            record['attributes'] = json.loads(record['attributes'])
        except (json.JSONDecodeError, TypeError):
            record['attributes'] = {}
    elif record.get('attributes') is None:
        record['attributes'] = {}
    return entity_edge_from_record(record)
