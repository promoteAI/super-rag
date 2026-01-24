import logging
import tempfile
from pathlib import Path
from typing import Any

from super_rag.fileparser.mineru_common import parse_doc
from super_rag.fileparser.base import BaseParser, FallbackError, Part, PdfPart
from super_rag.fileparser.parse_md import parse_md

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = [
    ".png", 
    ".jpeg", 
    ".jp2", 
    ".webp", 
    ".gif", 
    ".bmp", 
    ".jpg",
    ".pdf",
]


class MinerUParser(BaseParser):
    name = "mineru"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def supported_extensions(self) -> list[str]:
        return SUPPORTED_EXTENSIONS

    def parse_file(self, path: Path, metadata: dict[str, Any]={}, **kwargs) -> list[Part]:
        # 使用临时目录存放mineru输出，避免污染当前目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 临时目录下创建 mineru_output 目录
            output_dir = Path(temp_dir) / "mineru_output"
            output_dir.mkdir(parents=True, exist_ok=True)
            # 调用 parse_doc 进行解析
            parse_doc([path], output_dir=output_dir, backend="pipeline", **kwargs)
            # 构造 markdown 文件路径
            md_path = output_dir / f"{path.stem}/auto/{path.stem}.md"
            if not md_path.exists():
                raise FallbackError(f"未找到 mineru 生成的 markdown 文件: {md_path}")
            # 读取 markdown 内容
            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()
            return parse_md(md_content, metadata)

# --- For testing ---
if __name__ == "__main__":
    import os
    os.environ['MINERU_MODEL_SOURCE'] = "modelscope"
    parser = MinerUParser()
    print(parser.parse_file(Path("demo/Switch_Transformers copy.pdf")))
    
