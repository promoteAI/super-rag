

import shutil
from typing import Any, Dict, Iterator

from super_rag.objectstore.base import get_object_store
from super_rag.schema.view_models import CollectionConfig
from super_rag.source.base import LocalDocument, RemoteDocument, Source
from super_rag.source.utils import gen_temporary_file


class UploadSource(Source):
    def __init__(self, ctx: CollectionConfig):
        super().__init__(ctx)

    def scan_documents(self) -> Iterator[RemoteDocument]:
        return iter([])

    def prepare_document(self, name: str, metadata: Dict[str, Any]) -> LocalDocument:
        obj_path = metadata.get("object_path", "")
        if not obj_path:
            raise Exception("empty object path")
        obj_store = get_object_store()
        obj = obj_store.get(obj_path)
        if obj is None:
            raise Exception(f"object '{obj_path}' is not found")
        with gen_temporary_file(name) as temp_file, obj:
            shutil.copyfileobj(obj, temp_file)
            filepath = temp_file.name
        metadata["name"] = name
        return LocalDocument(name=name, path=filepath, metadata=metadata)

    def sync_enabled(self):
        return False
