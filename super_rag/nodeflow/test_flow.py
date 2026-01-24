
import os

from super_rag.nodeflow.engine import NodeflowEngine
from super_rag.nodeflow.parser import nodeflowParser
import asyncio
import json


async def test_rag_flow():
    """Test the RAG flow execution"""
    # Get current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_path = os.path.join(current_dir, "examples", "rag_flow3.yaml")

    import yaml

    # Load YAML as dict for inspection
    with open(yaml_path, 'r', encoding='utf-8') as f:
        yaml_dict = yaml.safe_load(f)
    print("YAML loaded as dict:")
    print(json.dumps(yaml_dict))

    # Load flow configuration
    flow = nodeflowParser.load_from_file(yaml_path)

    # print(flow)

    # Create execution engine
    engine = NodeflowEngine()

    # Execute flow with initial data
    initial_data = {"query": "What is the capital of France?","user": str(123)}

    try:
        res=await engine.execute_nodeflow(flow, initial_data)
        print(f"Flow executed successfully!{res}")
    except Exception as e:
        print(f"Error executing flow: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_rag_flow())
