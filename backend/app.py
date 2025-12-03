import logging
from manager import deepseek_chat
from langchain.agents import create_agent
from langchain.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, AIMessageChunk
from tools import smart_search
from prompt import system_prompt_template
from string import Template
from memory import global_memory
from conversations import insert_conversation, create_conversations
from knowledgebase import create_knowledgebase, save_file_to_knowledge
from fastapi import FastAPI, UploadFile, File, HTTPException
import asyncio
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import os
import tempfile
from typing import Optional
import json
from memory import global_memory

app = FastAPI(title="EasyRAG API", description="RAG Agent API", version="1.0.0")

# 基本日志配置
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger('easyRAG.app')
logger.info('Starting EasyRAG API')

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # 前端开发服务器地址
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)

# 初始化数据库集合
@app.on_event("startup")
async def startup_event():
    """服务启动时初始化数据库集合"""
    try:
        create_conversations()
        create_knowledgebase()
        print("数据库集合初始化完成")
    except Exception as e:
        print(f"数据库集合初始化失败: {e}")

tools = [smart_search]

agent = create_agent(
    model=deepseek_chat,
    tools=tools
)


class QuestionRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class SessionRequest(BaseModel):
    question: str

def get_all_conversateions():
    """获取所有对话记录（测试用）"""
    return global_memory.get_all_conversations()

def get_conversation_by_session(session_id: str):
    """根据 session_id 获取对话记录（测试用）"""
    return global_memory.get_by_session_id(session_id=session_id)

def ask_agent(question: str, session_id: str):
    """流式生成问答输出。返回一个同步生成器，每次产出一个 JSON 行（bytes），格式为 NDJSON。

    每个产出的行为 JSON 对象，形如:
        {"type": "ai"|"tool", "content": "..."}\n
    在流结束后，内部会把完整对话写入内存/数据库。
    """
    related_convs = global_memory.get_related_conversations(question, session_id=session_id, top_k=10)
    recent_convs = global_memory.get_recent_conversations(session_id=session_id, top_k=30)

    system_prompt = system_prompt_template.substitute({
        "related_conversation": related_convs,
        "recent_conversation": recent_convs
    })

    aimessage = ""
    # 收集工具调用结果，供最终生成结构化摘要
    collected_tool_results = []

    # 使用 stream_mode="messages" 获取流式消息
    # 这是最稳定且兼容的方式，agent 会逐步产出消息块（包含工具调用和 AI 回复）
    for chunk in agent.stream(
        {
            "messages": [
                SystemMessage(system_prompt),
                HumanMessage(content=question)
            ]
        },
        stream_mode="messages"
    ):
        # chunk 通常是 (message, metadata) 元组或直接是消息
        msg = chunk[0] if isinstance(chunk, tuple) else chunk
        
        if isinstance(msg, AIMessageChunk):
            piece = msg.content
            if piece:
                aimessage += piece
                obj = {"type": "ai", "content": piece}
                yield (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        elif isinstance(msg, ToolMessage):
            piece = msg.content
            tool_name = getattr(msg, 'name', 'unknown_tool')
            # 记录工具原始返回并尝试解析为 JSON，供后续 ai_final 使用
            parsed = None
            try:
                parsed = json.loads(piece)
            except Exception:
                parsed = None
            collected_tool_results.append({
                "tool_name": tool_name,
                "raw": piece,
                "parsed": parsed
            })
            try:
                print(f"[DEBUG] ToolMessage emitted: tool_name={tool_name} content_len={len(piece) if piece else 0}")
            except Exception:
                pass
            # 在工具执行前后发送状态事件，便于前端显示“检索中...”提示
            try:
                start_obj = {"type": "tool_start", "tool_name": tool_name}
                yield (json.dumps(start_obj, ensure_ascii=False) + "\n").encode("utf-8")
            except Exception:
                pass

            obj = {"type": "tool", "content": piece, "tool_name": tool_name}
            yield (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")

            try:
                done_obj = {"type": "tool_done", "tool_name": tool_name}
                yield (json.dumps(done_obj, ensure_ascii=False) + "\n").encode("utf-8")
            except Exception:
                pass

    # 流结束后，把完整对话插入记忆
    new_conversation = {
        "user_message": question,
        "ai_message": aimessage
    }
    global_memory.add_conversation(new_conversation, session_id=session_id)
    # 构建并发送一个最终的结构化事件，便于前端确定性渲染（sections / search_summary / references）
    try:
        # 简单汇总每个工具的返回，提取可用引用（优先 parsed 字段）
        refs = []
        seen_urls = set()
        search_summary = {}
        for tr in collected_tool_results:
            tname = tr.get('tool_name') or 'unknown'
            search_summary.setdefault(tname, 0)
            search_summary[tname] += 1

            parsed = tr.get('parsed')
            items = []
            if isinstance(parsed, dict):
                # 期望格式: {source: 'web'|'knowledge', items: [{title, url, snippet}, ...]}
                if 'items' in parsed and isinstance(parsed['items'], list):
                    items = parsed['items']
                else:
                    # 可能直接是 {url:..., title:...}
                    items = [parsed]
            elif isinstance(parsed, list):
                items = parsed
            else:
                # 解析失败，尝试从 raw 文本中抽取 URL
                raw = tr.get('raw') or ''
                import re
                urls = re.findall(r"https?://[^\s,'\)\"]+", raw)
                for u in urls:
                    items.append({'title': u, 'url': u, 'snippet': ''})

            for it in items:
                url = it.get('url') or it.get('link') or it.get('source')
                title = it.get('title') or it.get('name') or url
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    refs.append({'title': title, 'url': url})

        ai_final = {
            'type': 'ai_final',
            'intent_declaration': '',
            'search_summary': search_summary,
            'sections': [],
            'references': refs
        }

        yield (json.dumps(ai_final, ensure_ascii=False) + "\n").encode('utf-8')
    except Exception:
        pass


def ask_agent_sync(question: str, session_id: str) -> str:
    """消费 ask_agent 的流并返回完整回答的同步辅助函数（供非流式调用使用）。"""
    full = ""
    for chunk_bytes in ask_agent(question, session_id):
        try:
            obj = json.loads(chunk_bytes.decode("utf-8"))
        except Exception:
            continue
        if obj.get("type") == "ai":
            full += obj.get("content", "")
    return full


def start_new_session(question: str) -> dict:
    """开启新会话"""
    new_session = str(uuid.uuid4())
    answer = ask_agent(question, new_session)
    
    return {
        "session_id": new_session,
        "answer": answer
    }


# ============== API 端点 ==============

@app.post("/api/chat")
async def chat(request: QuestionRequest):
    """
    聊天接口
    - 如果提供 session_id，则继续现有会话
    - 如果不提供，则创建新会话
    """
    try:
        logger.info('Received /api/chat request', extra={'question_len': len(request.question or ''), 'session_id': request.session_id})
        # 如果提供 session_id，则流式返回问答；如果不提供则创建新会话并先返回 session id
        if request.session_id:
            gen = ask_agent(request.question, request.session_id)
            return StreamingResponse(gen, media_type="application/x-ndjson")
        else:
            new_session = str(uuid.uuid4())

            async def stream_with_session():
                # 首先发送会话 id
                meta = {"type": "session", "content": new_session}
                yield (json.dumps(meta, ensure_ascii=False) + "\n").encode("utf-8")
                # 然后转发 ask_agent 的流
                for chunk in ask_agent(request.question, new_session):
                    yield chunk
                    # 强制刷新缓冲区，确保立即发送
                    await asyncio.sleep(0)

            return StreamingResponse(stream_with_session(), media_type="application/x-ndjson")
    except Exception as e:
        logger.exception('Error in /api/chat')
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/new")
async def create_session(request: SessionRequest):
    """创建新会话"""
    try:
        result = start_new_session(request.question)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}


@app.get("/api/conversations/all")
async def get_all_conversations():
    """获取所有对话记录"""
    try:
        # 从 Memory 获取分组的对话记录
        # 格式: {session_id: [{'id': '...', 'content': {...}, 'timestamp': ...}, ...]}
        grouped_conversations = get_all_conversateions()
        
        # 转换为前端期望的扁平列表格式
        conversations = []
        for session_id, convs in grouped_conversations.items():
            for conv in convs:
                conversations.append({
                    "session_id": session_id,
                    "user_message": conv['content']['user_message'],
                    "ai_message": conv['content']['ai_message'],
                    "timestamp": conv.get('timestamp')
                })
        
        return {
            "success": True,
            "conversations": conversations
        }
    except Exception as e:
        import traceback
        traceback.print_exc()  # 打印完整的错误堆栈
        raise HTTPException(status_code=500, detail=str(e))


class SessionIdRequest(BaseModel):
    session_id: str


@app.post("/api/conversations/get")
async def get_conversation_by_session_api(request: SessionIdRequest):
    """根据 session_id 获取对话记录"""
    try:
        # 获取该会话的所有对话
        # 格式: [{'id': '...', 'content': {...}, 'timestamp': ...}, ...]
        convs = get_conversation_by_session(request.session_id)
        
        # 转换为前端期望的格式
        conversations = []
        for conv in convs:
            conversations.append({
                "user_message": conv['content']['user_message'],
                "ai_message": conv['content']['ai_message'],
                "timestamp": conv.get('timestamp')
            })
        
        return {
            "success": True,
            "session_id": request.session_id,
            "conversations": conversations
        }
    except Exception as e:
        import traceback
        traceback.print_exc()  # 打印完整的错误堆栈
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/conversations/delete")
async def delete_conversation_api(request: SessionIdRequest):
    """删除指定 session_id 的所有对话记录"""
    try:
        deleted_count = global_memory.delete_conversation(request.session_id)
        
        return {
            "success": True,
            "session_id": request.session_id,
            "deleted_count": deleted_count,
            "message": f"成功删除 {deleted_count} 条对话记录"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    上传文件到知识库
    支持的文件类型: pdf, docx, pptx, txt, md
    文件将被解析、切片并向量化存储到 Milvus
    文件大小限制: 最大 20MB
    """
    from file_parser import is_supported_file
    
    # 检查文件类型
    if not is_supported_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file.filename}. 支持的类型: pdf, docx, pptx, txt, md"
        )
    
    # 读取文件内容并检查大小
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)  # 转换为 MB
    
    if file_size_mb > 20:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大: {file_size_mb:.2f}MB. 最大允许 20MB"
        )
    
    # 创建上传目录
    upload_dir = os.path.join(".", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    
    # 生成唯一文件名（避免重复）
    import time
    timestamp = int(time.time() * 1000)
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(upload_dir, safe_filename)
    
    try:
        # 保存文件
        with open(file_path, "wb") as f:
            f.write(content)
        
        # 解析并存入知识库
        result = save_file_to_knowledge(file_path)
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "file_path": file_path,
                "file_size_mb": round(file_size_mb, 2),
                "chunks_count": result["chunks_count"],
                "ids": result["ids"]
            }
        else:
            # 如果处理失败，删除文件
            if os.path.exists(file_path):
                os.unlink(file_path)
            raise HTTPException(status_code=500, detail=result["message"])
    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except Exception as e:
        # 确保删除文件
        if os.path.exists(file_path):
            os.unlink(file_path)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
