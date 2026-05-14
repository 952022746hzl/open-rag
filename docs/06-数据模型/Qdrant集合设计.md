# Qdrant 集合设计

> 所属模块：数据模型 | 来源章节：§12.2 | [← 返回主索引](../需求文档.md)

---

## 集合配置

```
Collection: factory_chunks
  Distance:          Cosine
  Vector Size:       1024（text-embedding-v3）
  on_disk_payload:   true
```

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
