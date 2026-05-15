"""文档分块器。

使用 tiktoken cl100k_base 编码将解析后的文档按 512 token 窗口、128 token 重叠切分，
每节独立分块以保留 source_location 元数据。
"""

from dataclasses import dataclass

import tiktoken

from app.core.parsers import ParsedDocument

_CHUNK_SIZE = 512
_OVERLAP = 128


@dataclass
class Chunk:
    """单个文本分块。

    Attributes:
        content: 分块的纯文本内容。
        tokens: 该分块的 token 数量。
        source_location: 来源位置标识，继承自所属节；无来源时为 None。
        chunk_index: 文档内全局序号，从 0 开始递增。
    """

    content: str
    tokens: int
    source_location: str | None
    chunk_index: int


def chunk_document(doc: ParsedDocument) -> list[Chunk]:
    """将解析后的文档切分为带元数据的分块列表。

    每个 ParsedSection 独立分块，各节的 source_location 随分块继承。
    空节跳过，不产生分块。

    Args:
        doc: 由 parse_document 返回的结构化文档对象。

    Returns:
        按文档顺序排列的 Chunk 列表，chunk_index 全局连续。
    """
    enc = tiktoken.get_encoding("cl100k_base")
    chunks: list[Chunk] = []
    chunk_index = 0

    for section in doc.sections:
        content = section.content.strip()
        if not content:
            continue

        token_ids = enc.encode(content)
        start = 0
        while start < len(token_ids):
            end = min(start + _CHUNK_SIZE, len(token_ids))
            window = token_ids[start:end]
            chunks.append(Chunk(
                content=enc.decode(window),
                tokens=len(window),
                source_location=section.source_location,
                chunk_index=chunk_index,
            ))
            chunk_index += 1
            if end == len(token_ids):
                break
            start += _CHUNK_SIZE - _OVERLAP

    return chunks
