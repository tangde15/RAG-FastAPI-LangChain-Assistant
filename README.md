# Custom-built AI Assistant

本项目为前后端分离的智能助手系统，支持知识库检索与联网搜索，采用 React+Vite 前端与 FastAPI/LangChain 后端。

## 目录结构（核心部分）

```
├── config.env.example      # 环境变量示例（复制并编辑为 config.env）
├── README.md               # 项目文档
├── CHANGELOG.md            # 变更日志
├── DEPLOYMENT.md           # 部署说明
├── docker-compose.yml      # 可选容器化部署
├── deploy.sh               # 本地/服务器启动脚本
├── backend/                # FastAPI 后端
│   ├── app.py              # FastAPI 应用入口（含流式接口+上传）
│   ├── manager.py          # 初始化模型、Milvus 客户端与 embedding 封装
│   ├── file_parser.py      # 文件解析模块（PDF/DOCX/PPTX/TXT/MD）
│   ├── knowledgebase.py    # Milvus 向量检索（批量插入+查询）
│   ├── requirements.txt    # Python 依赖
│   └── uploads/            # 运行时上传目录（被 .gitignore 忽略）
├── frontend/               # React + Vite 前端
│   ├── index.html
│   └── src/
├── scripts/                # 数据导入脚本（Hybrid extractor 等）
├── retrieval/              # reranker / 检索相关实现
├── utils/                  # 辅助工具（context_aware_split 等）
├── static/                 # 静态资源
└── 处理日志/               # 调试/运行日志（被 .gitignore 忽略）
```



## 主要功能

- ✅ Milvus 向量知识库检索（可选）与 BGE Embedding 支持（默认 `BAAI/bge-m3`，向量维度 1024）。
- ✅ Hybrid 文件解析（`unstructured` + `python-pptx` + PaddleOCR）：支持结构化文本、表格、SmartArt，以及图片中文字提取（OCR）。
- ✅ Embeddings 批量请求与重试：通过 SiliconFlow/OpenAI 兼容 API 批量获取向量，默认分批（可配置）。
- ✅ 自动文本切片（BGEChunker）：语义级别按句子+token 切片，默认 `chunk_size=300`、`overlap=50`，提高 embedding 效果与召回质量。
- ✅ 联网搜索（DuckDuckGo）+ 多轮重写 + Reranker（BGE reranker）以补充检索结果。
- ✅ 流式对话响应（FastAPI + LangChain），前端使用 React+Vite，支持工具卡片与文件上传。
- ✅ 运维友好：提供 Docker Compose、部署脚本与变更日志，支持快速复现与调试。

详细实现与配置请参见各子目录（`backend/`、`retrieval/`、`scripts/`）。

## BGE 优化点

本项目在以下核心环节全面采用 BGE（BAAI General Embedding）体系，显著提升中文检索与语义相关性：

- **BGE 语义切片**：
  - 文件解析后，采用 BGEChunker 按句子+token 级别切片，chunk_size=300，overlap=50，确保每个片段适配 BGE embedding 最优效果。
- **BGE Embedding 向量化**：
  - 默认使用 `BAAI/bge-m3`（可配置）作为 embedding 模型，生成高质量语义向量，支持中文多场景。
- **BGE Reranker 精排**：
  - 检索召回后，使用 `BAAI/bge-reranker-large` 进行语义精排，提升最终返回结果的相关性和准确率。
- **配置灵活**：
  - 相关模型名称、参数均可在 `config.env` 配置，便于自定义和升级。

上述优化已在 `file_parser.py`、`retrieval/reranker.py`、`manager.py` 等核心模块实现，详见代码与文档说明。

## 配置说明

编辑 `config.env` 文件（请根据实际密钥替换占位符）：

```env
SILICONFLO_API_KEY=your_siliconflo_api_key
SILICONFLO_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLO_EMBEDDING_MODEL=BAAI/bge-m3

DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com

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
**主要依赖（项目当前环境）**：
- FastAPI `0.121.1` + Uvicorn `0.38.0`
- LangChain `1.0.3` + LangGraph `1.0.3`
- pymilvus `2.6.2`
- FlagEmbedding `1.2.10`（BAAI/bge-m3 向量模型）
- pdfplumber `0.11.8`、python-docx `1.2.0`、python-pptx `1.0.2`（文件解析）
- requests `2.32.5` + beautifulsoup4 `4.14.3`（联网搜索）
- paddleocr `3.3.0`, paddlepaddle `3.2.2`, paddlex `3.3.10`
- opencv-python `4.12.0.88`, numpy `2.2.6`

注意：依赖会随项目迭代更新，实际安装环境以 `backend/requirements.txt` 为准。

推荐 Python 版本：**3.10 或 3.11**（部分二进制包如 PyMuPDF、paddleocr 对 Python 3.12/3.13 的支持有限，使用 3.10/3.11 可获得更好兼容性，本项目使用Python 3.12,需要修改部分依赖源码）。

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

### PPT / PDF 图片 OCR 优化（重要）

本项目对 PPT 和 PDF 的图片文字识别做了兼容与稳定性优化，关键点如下：

- 使用 `unstructured` + `python-pptx` + PaddleOCR 的混合解析器（Hybrid-PPT-Extractor），保证结构化内容与图片文字都能被提取。
- 在传入 PaddleOCR 前，确保将 `PIL.Image` 转为 `numpy.ndarray`（BGR），或传入本地图片路径，避免 PaddleOCR 忽略 `PIL.Image` 对象。
- 对 PaddleOCR 的 API 兼容性做了保护：通过检查函数签名决定是否传入 `cls` 参数，并使用单例模式初始化 OCR 实例，避免重复初始化错误。
- 向量化上传做了分批与重试机制，避免单次请求过大导致的 413 错误。

快速建议：如遇图片文字未识别，请确认 `opencv-python` 是否安装（用于从 PIL 转为 numpy），并查看后端日志中是否有 `[OCR] 识别异常` 或 `[向量化]` 相关输出。

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


## 🛠️ 快速部署与配置步骤

### 1. 克隆项目代码
```bash
git clone <你的仓库地址>
cd Custom-built AI assistant
```

### 2. 安装依赖
#### 后端依赖
```bash
cd backend
pip install -r requirements.txt
```
#### 前端依赖
```bash
cd frontend
npm install
```

### 3. 配置环境变量
项目根目录有 `config.env.example` 文件，**不要直接上传真实密钥到 GitHub**。
1. 复制模板文件：
   ```bash
   cp config.env.example config.env
   ```
2. 编辑 `config.env`，填写你的 API 密钥和参数（如 DeepSeek、SiliconFlow、Milvus 等）。
  示例内容：
  ```env
  SILICONFLO_API_KEY=你的SiliconFlow密钥
  SILICONFLO_BASE_URL=https://api.siliconflow.cn/v1
  SILICONFLO_EMBEDDING_MODEL=BAAI/bge-m3

  DEEPSEEK_API_KEY=你的DeepSeek密钥
  DEEPSEEK_BASE_URL=https://api.deepseek.com

  MILVUS_HOST=127.0.0.1
  MILVUS_PORT=19530
  MILVUS_DATABASE=AI
  ```

### 4. 启动后端服务
```bash
cd backend
python app.py
# 或
uvicorn app:app --host 0.0.0.0 --port 8000
```
访问后端接口：`http://localhost:8000`

### 5. 启动前端服务
```bash
cd frontend
npm run dev
```
访问前端页面：`http://localhost:5173`（或终端提示端口）

### 6. 文件上传与知识入库
- 支持 PDF、DOCX、PPTX、TXT、MD 文件
- 上传接口：`POST /api/knowledge/upload`
- 上传目录：`backend/uploads/`（自动创建）

### 7. 常见问题排查
- Milvus 连接失败：检查 `config.env` 配置，确保 Milvus 服务已启动
- 文件上传失败：检查格式和大小，确认 `backend/uploads/` 有写权限
- 向量化失败：确保 FlagEmbedding 安装并能下载模型
- 联网搜索无结果：检查网络或更换搜索引擎

---

## 🆕 近期优化与重要变更
- **依赖兼容性**：已解决多项依赖冲突并改进安装说明；请以 `backend/requirements.txt` 为准进行环境复现（部分可选组件如 `peft` 可能仍在 requirements 中，按需启用）。
- **检索与精排升级**：检索流程调整为 Milvus topk=200 → reranker 精排 topk=50 → 最终返回 5 条，提升召回与排序质量。
- **BGE 语义切片**：采用 BGEChunker 按句子+token（默认 chunk_size=300, overlap=50）进行语义切片，提高向量化与检索效果。
- **PPT / PDF 图片 OCR 优化**：新增 Hybrid-PPT-Extractor（`unstructured` + `python-pptx` + PaddleOCR），修复图片文字“被跳过”问题：
  - 将 `PIL.Image` 转为 `numpy.ndarray`（BGR）或传入临时文件路径以兼容 PaddleOCR；
  - 在调用前检查 OCR 方法签名，只有支持 `cls` 参数时才传入，避免 unexpected keyword 错误；
  - 使用 OCR 单例与线程安全初始化，避免重复初始化导致的内部错误。
- **向量化稳定性**：embeddings 上传采用分批（默认 batch_size=16，可通过 `SILICONFLO_EMBEDDING_BATCH_SIZE` 环境变量调整）与重试机制，降低单次请求体过大（413）与网络抖动风险。
- **环境清理与恢复建议**：提供 `pip cache purge`、升级 `pip`、在无 GPU 时可安全执行 `torch.cuda.empty_cache()` 等命令以清理环境与显存。
- **文档与日志**：已更新 `README.md`、`DEPLOYMENT.md`、`CHANGELOG.md`，并补充 `模型识别不到文件内图片内容.txt` 日志，记录问题定位与修复过程。

---
如有问题请提 issue 或联系作者。



