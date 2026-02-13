"""示例节点：回显（Echo）。"""

from typing import Any, Dict, Tuple

from pydantic import BaseModel, Field

from super_rag.nodeflow.base.models import BaseNodeRunner, SystemInput, register_node_runner


class EchoInput(BaseModel):
    message: str = Field("", description="Echo message")


class EchoOutput(BaseModel):
    text: str


@register_node_runner("echo", input_model=EchoInput, output_model=EchoOutput)
class EchoNodeRunner(BaseNodeRunner):
    """示例：回显节点，将 message 或 query 原样输出。"""

    async def run(self, ui: EchoInput, si: SystemInput) -> Tuple[EchoOutput, Dict[str, Any]]:
        text = ui.message.strip() or getattr(si, "query", "") or ""
        return EchoOutput(text=text), {}
