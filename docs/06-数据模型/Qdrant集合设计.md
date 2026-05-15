# Qdrant 集合设计

> 所属模块：数据模型 | 来源章节：§12.2 | [← 返回主索引](../需求文档.md)

---

## 集合配置

```
Collection: factory_chunks
  向量配置（命名向量）：
    dense:   VectorParams(size=1536, distance=Cosine)   # text-embedding-3-small
    sparse:  SparseVectorParams()                        # fastembed BM25
  on_disk_payload: true
```

> 混合检索：检索时对 dense 和 sparse 分别执行 prefetch，再用 RRF（Reciprocal Rank Fusion）融合两路排名，兼顾语义相似度和关键字精确匹配。

---

## Payload 字段

全部字段支持过滤（filter）：

```
document_id       integer
chunk_id          integer   ← Point ID，与 document_chunks.id 一致
chunk_index       integer
document_name     string
file_type         string
uploader_id       integer   ← 用于 private 可见范围过滤
department_id     integer   ← 用于 department 可见范围过滤（可为 null）
visibility_scope  string    ← public / department / private
tags              string[]
upload_date       integer   ← Unix 时间戳
source_location   string
snippet           string    ← 分块前 200 字符
```
