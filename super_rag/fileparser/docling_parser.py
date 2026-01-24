import tempfile
from pathlib import Path
from typing import Any

from docling.document_converter import DocumentConverter
from docling_core.types.doc.base import ImageRefMode

from super_rag.fileparser.base import BaseParser, FallbackError, Part
from super_rag.fileparser.parse_md import parse_md
from super_rag.fileparser.utils import convert_office_doc, get_soffice_cmd

SUPPORTED_EXTENSIONS = [
    ".txt",
    ".text",
    ".md",
    ".markdown",
    ".html",
    ".htm",
    ".docx",
    ".doc",  # convert to .docx first
    ".xlsx",
    ".xls",
    ".pptx",
    ".ppt",  # convert to .pptx first
    ".pdf",
]


class DoclingParser(BaseParser):
    name = "docling"

    def supported_extensions(self) -> list[str]:
        return SUPPORTED_EXTENSIONS

    def parse_file(self, path: Path, metadata: dict[str, Any] = {}, **kwargs) -> list[Part]:
        extension = path.suffix.lower()
        target_format = None
        if extension == ".doc":
            target_format = ".docx"
        elif extension == ".ppt":
            target_format = ".pptx"
        if target_format:
            if get_soffice_cmd() is None:
                raise FallbackError("soffice command not found")
            with tempfile.TemporaryDirectory() as temp_dir:
                converted = convert_office_doc(path, Path(temp_dir), target_format)
                return self._parse_file(converted, metadata, **kwargs)
        return self._parse_file(path, metadata, **kwargs)

    def _parse_file(self, path: Path, metadata: dict[str, Any] = {}, **kwargs) -> list[Part]:
        converter = DocumentConverter()
        result = converter.convert(path)
        md_content=result.document.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)
        return parse_md(md_content, metadata)

if __name__ == "__main__":
    parser = DoclingParser()
    print(parser.parse_file(Path("/home/tarena/code/workspace/super-learner/demo/首都民生谱新篇.docx")))