"""稀疏向量编码器，使用 fastembed BM25 模型。

BM25 对 CJK 字符做 character-level tokenization，
"郝子樑" 会被识别为独立字符 token，在包含该字符序列的文档中得到高 TF 权重，
与 text-embedding-3-small 的语义向量形成互补，解决命名实体查询定向问题。

首次调用会从 HuggingFace 下载词表（约 10 MB），后续复用内存中的模型实例。
"""

from fastembed import SparseTextEmbedding
from qdrant_client.models import SparseVector

_MODEL_NAME = "Qdrant/bm25"
_model: SparseTextEmbedding | None = None


def _get_model() -> SparseTextEmbedding:
    global _model
    if _model is None:
        _model = SparseTextEmbedding(model_name=_MODEL_NAME)
    return _model


def encode_sparse(texts: list[str]) -> list[SparseVector]:
    """将文本列表编码为 BM25 稀疏向量。

    纯 CPU 操作，速度远快于 Embedding API 调用，调用者无需 await。

    Args:
        texts: 待编码的文本列表，长度任意。

    Returns:
        与输入等长的 SparseVector 列表，每个向量仅含非零位的 indices 和 values。
    """
    model = _get_model()
    return [
        SparseVector(indices=emb.indices.tolist(), values=emb.values.tolist())
        for emb in model.embed(texts)
    ]
