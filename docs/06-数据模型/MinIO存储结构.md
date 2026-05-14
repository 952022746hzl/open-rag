# MinIO 存储结构

> 所属模块：数据模型 | 来源章节：§12.3 | [← 返回主索引](../需求文档.md)

---

## Bucket 与路径规范

```
Bucket: factory-documents
  {yyyyMMdd-HHmmss}/{document_id}/{yyyyMMdd-HHmmss}_{original_filename}

示例：
  20260513/42/20260513-143022_作业指导_焊接.pdf
  20260513/43/20260513-150011_物料规格_铝合金.docx
```

详细存储策略见 [对象存储设计](../02-文档管理/对象存储设计.md)。
