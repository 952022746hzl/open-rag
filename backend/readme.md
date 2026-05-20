  # 1. 安装依赖（在 backend/ 目录下）
  pip install -r requirements.txt

  # 2. 生成 RSA 密钥
  python scripts/generate_keys.py

  # 3. 复制并填写 .env
  copy .env.example .env
  # 用编辑器打开 .env，填入 DATABASE_URL 和 INIT_ADMIN_PASSWORD

  .env 中的 DATABASE_URL 格式：

  DATABASE_URL=postgresql+psycopg://用户名:密码@主机地址:5432/数据库名
  

    # 4 下载rerank模型
    
python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-v2-m3')"