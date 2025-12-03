
# Custom-built AI Assistant

本项目为前后端分离的智能助手系统，支持知识库检索与联网搜索，采用 React+Vite 前端与 FastAPI/LangChain 后端。**easyRAG 目录及其内容已不再参与主流程，可直接删除。**

## 目录结构（核心部分）

```
├── config.env              # 环境变量配置
├── README.md               # 项目文档
├── backend/                # FastAPI 后端
│   ├── agent.py           # LangGraph Agent 核心逻辑
│   ├── app.py             # FastAPI 应用入口（含流式接口+上传）
│   ├── file_parser.py     # 文件解析模块（PDF/DOCX/PPTX/TXT/MD）
│   ├── knowledgebase.py   # Milvus 向量检索（批量插入+查询）
│   ├── memory.py          # 多轮对话记忆管理
│   ├── prompt.py          # Prompt 模板
│   ├── tools.py           # 工具集（search_knowledge/search_internet）
│   ├── conversations.py   # 对话历史存储
│   └── requirements.txt   # Python 依赖
├── frontend/               # React+Vite+TS 前端
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── global.css
│       ├── pages/Chat.tsx
│       ├── components/MarkdownMessage.tsx
│       ├── components/ToolOutput.tsx
│       └── lib/api.ts
├── scripts/                # 数据导入等脚本
└── static/                 # 静态资源
```

> ⚠️ `easyRAG/` 及其子目录为历史参考实现，当前主流程完全不依赖，可安全删除。

## 主要功能

- ✅ Milvus 向量知识库检索（可选）
- ✅ 智能判断是否需要联网搜索（DDG+多轮重写+摘要+Rerank）
- ✅ 流式对话响应，支持工具卡片插入
- ✅ React+Vite+TS 前端，深色卡片风格
- ✅ FastAPI/LangChain 后端，接口统一
- ✅ 文件上传与解析（PDF/DOCX/PPTX/TXT/MD）
- ✅ 自动文本切片与向量化存储

## 配置说明

编辑 `config.env` 文件：

```env
SILICONFLO_API_KEY=your_api_key
SILICONFLO_MODEL=deepseek-ai/DeepSeek-R1-Distill-Qwen-32B
SILICONFLO_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLO_EMBEDDING_MODEL=BAAI/bge-m3
MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530
MILVUS_DATABASE=AI
```

## 安装依赖

### 后端
```bash
cd backend
pip install -r requirements.txt
```

**主要依赖**：
- FastAPI 0.115.0 + Uvicorn 0.30.1
- LangChain 0.3.10 + LangGraph
- pymilvus 2.5.1
- FlagEmbedding 1.3.3（BAAI/bge-m3 向量模型）
- pdfplumber 0.11.4、python-docx 1.1.2、python-pptx 1.0.2（文件解析）
- requests 2.32.3 + beautifulsoup4 4.12.3（联网搜索）

### 前端
```bash
cd frontend
npm install
```

## 启动方式

### 1. 启动后端
```bash
cd backend
python app.py
# 或
uvicorn app:app --host 0.0.0.0 --port 8000
```
后端接口地址：`http://localhost:8000`

### 2. 启动前端
```bash
cd frontend
npm run dev
```
前端开发地址：`http://localhost:5173`（或终端提示端口）

## 使用说明

### 核心流程
1. **知识库检索**：优先从 Milvus 知识库中检索相关信息
2. **智能判断**：如知识库无高分结果，自动多轮联网搜索（DDG+重写+摘要+Rerank）
3. **流式响应**：AI/工具卡片实时插入，体验流畅

### 文件上传与知识入库
- **支持格式**：PDF、DOCX、PPTX、TXT、MD
- **上传限制**：单文件最大 20MB
- **处理流程**：
  1. 文件解析提取文本
  2. 自动切片（默认 500 字符/块，100 字符重叠）
  3. 向量化（BAAI/bge-m3 Embedding）
  4. 批量存储到 Milvus
- **接口地址**：`POST /api/knowledge/upload`
- **上传目录**：`backend/uploads/`（自动创建）

## API 说明

### POST /api/chat
流式聊天接口，支持 session_id 续聊
```json
{
  "question": "你的问题",
  "session_id": "可选，会话ID"
}
```
响应：NDJSON 流
- `{"type": "session", "content": "session_id"}`
- `{"type": "ai", "content": "回答内容"}`
- `{"type": "tool", "content": "...", "tool_name": "..."}`

### POST /api/knowledge/upload
文件上传与入库接口
```bash
curl -X POST http://localhost:8000/api/knowledge/upload \
  -F "file=@sample.pdf"
```
响应：
```json
{
  "success": true,
  "message": "文件上传并入库成功",
  "file_path": "backend/uploads/20240101_120000_sample.pdf",
  "file_size_mb": 1.23,
  "chunks_count": 45,
  "ids": ["449747374563623811", "449747374563623812", ...]
}
```

### GET /api/health
健康检查

## 常见问题

### 1. Milvus 连接问题
Milvus 可选，未启用时知识库检索自动降级为联网搜索。检查 `config.env` 中的 `MILVUS_HOST` 和 `MILVUS_PORT` 配置。

### 2. 文件上传失败
- 检查文件格式是否为 PDF/DOCX/PPTX/TXT/MD
- 检查文件大小是否超过 20MB
- 确认 `backend/uploads/` 目录有写入权限

### 3. 向量化失败
确保已安装 FlagEmbedding 并可访问 `BAAI/bge-m3` 模型（首次使用会自动下载约 2GB）。

### 4. 联网搜索不返回结果
DuckDuckGo 在中国大陆可访问，但如遇问题可检查网络连接或更换搜索引擎。

### 5. 前端样式自定义
编辑 `frontend/src/global.css` 修改主题/颜色/卡片样式。

### 6. easyRAG 目录
`easyRAG/` 为历史参考实现，不影响主流程，可安全删除。

---
如有问题请提 issue 或联系作者。



