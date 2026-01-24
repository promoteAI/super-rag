import os
from typing import Callable, List

import tiktoken


def get_default_tokenizer() -> Callable[[str], List[int]]:
    encoding = tiktoken.get_encoding(os.environ.get("DEFAULT_ENCODING_MODEL", "cl100k_base"))
    return encoding.encode
