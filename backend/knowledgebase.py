from pymilvus import DataType
import json
from manager import milvus_client, embedding_model
from uuid import uuid4
from file_parser import read_file, chunk_text, is_supported_file
from typing import List
import os

def create_knowledgebase():
    if milvus_client.has_collection("knowledgebase"):
        print("Collection 'knowledgebase' already exists.")
        return

    # 创建集合模式（Schema）
    schema = milvus_client.create_schema(
        auto_id=True,
        enable_dynamic_fields=True,
    )

    # 添加字段
    schema.add_field(
        field_name="id", 
        datatype=DataType.VARCHAR, 
        is_primary=True, 
        max_length=100
    )
    schema.add_field(
        field_name="content",
        datatype=DataType.VARCHAR,
        max_length=65535
    )
    schema.add_field(
        field_name="dense_vector", 
        datatype=DataType.FLOAT_VECTOR, 
        # dim 指定向量维度
        dim=1024
    )
    schema.add_field(
        field_name="source",
        datatype=DataType.VARCHAR,
        max_length=65535
    )
    schema.add_field(
        field_name="timestamp",
        datatype=DataType.DOUBLE
    )
    
    # 创建索引
    index_params = milvus_client.prepare_index_params()

    index_params.add_index(
        field_name="id",
        index_type="AUTOINDEX"
    )

    index_params.add_index(
        field_name="dense_vector", 
        index_type="AUTOINDEX",
        metric_type="COSINE"
    )

    # 创建集合
    milvus_client.create_collection(
        collection_name="knowledgebase",
        schema=schema,
        index_params=index_params
    )

    res = milvus_client.get_load_state(
        collection_name="knowledgebase"
    )

    print(res)

def insert_knowledge(knowledge: dict):
    """
    插入知识到知识库
    knowledge: {
        "content": "知识内容",
        "source": "知识来源"
    }
    """
    vector = embedding_model.encode([knowledge["content"]])['dense_vecs'][0]

    from datetime import datetime

    now = datetime.now()
    timestamp = now.timestamp()

    res = milvus_client.insert(
        collection_name="knowledgebase",
        data=[{
            "content": knowledge["content"],
            "dense_vector": vector,
            "source": knowledge["source"],
            "timestamp": timestamp
        }]
    )

    print(f"Inserted knowledge, ID: {res['ids'][0]}")

    return res['ids'][0]


def search_knowledge(query: str, top_k: int = 5):
    query_vector = embedding_model.encode([query])['dense_vecs'][0]
    res = milvus_client.search(
        collection_name="knowledgebase",
        data=[query_vector],
        limit=top_k,
    )

    data = []
    for hits in res:
        for hit in hits:
            # 提取相似度分数（Milvus 2.x 使用 'distance' 字段）
            score = None
            hit_id = None
            
            if isinstance(hit, dict):
                score = hit.get('distance')
                hit_id = hit.get('id')
            else:
                # 如果不是字典，尝试作为对象访问属性
                try:
                    score = getattr(hit, 'distance', None)
                    hit_id = getattr(hit, 'id', None)
                except Exception:
                    pass
            
            print(f"[知识库检索] ID: {hit_id}, 相似度分数: {score}")
            
            if not hit_id:
                continue
            
            try:
                entity = milvus_client.get(
                    collection_name="knowledgebase",
                    ids=[hit_id],
                    output_fields=["id", "content", "source", "timestamp"]
                )
                if entity and len(entity) > 0:
                    ent = entity[0]
                    ent['score'] = score
                    ent['similarity'] = score  # Milvus distance 本身就是相似度
                    data.append(ent)
            except Exception as e:
                print(f"[知识库检索] 获取实体失败: {e}")
                # 如果查询失败，创建一个最小化的结果
                data.append({'id': hit_id, 'score': score, 'similarity': score, 'content': '', 'source': ''})

    return data


def insert_knowledge_batch(chunks: List[str], source: str):
    """
    批量插入知识片段到知识库
    
    Args:
        chunks: 文本片段列表
        source: 知识来源（文件名或URL）
    
    Returns:
        插入的记录ID列表
    """
    if not chunks:
        return []
    
    from datetime import datetime
    timestamp = datetime.now().timestamp()
    
    # 批量编码所有片段
    print(f"[向量化] 开始向量化 {len(chunks)} 个文本片段...")
    vectors = embedding_model.encode(chunks)['dense_vecs']
    print(f"[向量化] 向量化完成，生成 {len(vectors)} 个向量")
    
    # 准备插入数据
    print(f"[知识库] 准备插入 {len(chunks)} 条知识到 Milvus...")
    data = []
    for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
        data.append({
            "content": chunk,
            "dense_vector": vector,
            "source": source,
            "timestamp": timestamp
        })
    
    # 批量插入
    res = milvus_client.insert(
        collection_name="knowledgebase",
        data=data
    )
    
    ids = [int(id) for id in res['ids']]
    print(f"[知识库] 成功插入 {len(chunks)} 条知识，ID: {ids[0]} ~ {ids[-1]}")
    # 将 Milvus 返回的 ids 转换为普通 Python 列表
    return ids


def save_file_to_knowledge(file_path: str, chunk_size: int = 500, overlap: int = 50):
    """
    将文件内容解析、切片并保存到知识库
    
    Args:
        file_path: 文件路径
        chunk_size: 每个片段的最大字符数（默认 500，强制范围 500-1000）
        overlap: 片段之间的重叠字符数（默认 50）
    
    Returns:
        dict: {
            "success": bool,
            "message": str,
            "ids": list,
            "chunks_count": int
        }
    """
    try:
        filename = os.path.basename(file_path)
        print(f"\n{'='*60}")
        print(f"[上传处理] 开始处理文件: {filename}")
        print(f"{'='*60}")
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return {
                "success": False,
                "message": f"文件不存在: {file_path}",
                "ids": [],
                "chunks_count": 0
            }
        
        # 检查文件类型
        if not is_supported_file(filename):
            return {
                "success": False,
                "message": f"不支持的文件类型: {filename}",
                "ids": [],
                "chunks_count": 0
            }
        
        # 解析文件内容
        # === 新增：PPTX 用 Hybrid-PPT-Extractor，其他用原有解析 ===
        elements = None
        if filename.lower().endswith(".pptx"):
            try:
                from scripts.hybrid_ppt_extractor import extract_all
                print("[PPTX] 使用 Hybrid-PPT-Extractor 提取内容...")
                # extract_all 返回大文本，按段落分割
                ppt_text = extract_all(file_path)
                # 兼容性处理：按换行拆分
                raw_texts = [t for t in ppt_text.split("\n") if t.strip()]
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[PPTX] Hybrid-PPT-Extractor 失败: {e}")
                raw_texts = []
        else:
            raw_text = read_file(file_path)
            if not raw_text or not raw_text.strip():
                return {
                    "success": False,
                    "message": "文件内容为空",
                    "ids": [],
                    "chunks_count": 0
                }
            raw_texts = [raw_text]

        # 智能切片（context_aware_split）
        try:
            from utils.context_aware_split import context_aware_split
            # 强制限制 chunk_size 在 500-1000 范围内
            chunk_size = max(500, min(1000, chunk_size))
            chunks = []
            for text in raw_texts:
                pieces = context_aware_split(text, max_len=chunk_size, overlap=overlap)
                chunks.extend([p for p in pieces if p.strip()])
        except Exception as e:
            print(f"[切片] context_aware_split 失败: {e}，使用简单切片")
            import traceback
            traceback.print_exc()
            # 备用：简单切片（按固定长度）
            chunk_size = max(500, min(1000, chunk_size))
            chunks = []
            for text in raw_texts:
                if len(text) <= chunk_size:
                    chunks.append(text)
                else:
                    # 按 chunk_size 切片
                    for i in range(0, len(text), chunk_size - overlap):
                        chunk = text[i:i + chunk_size]
                        if chunk.strip():
                            chunks.append(chunk)

        # 验证并强制切片超长 chunks
        validated_chunks = []
        for chunk in chunks:
            if len(chunk) <= 1000:
                validated_chunks.append(chunk)
            else:
                # 超长 chunk 强制二次切片
                print(f"[切片] 检测到超长 chunk ({len(chunk)} 字符)，强制切分...")
                for i in range(0, len(chunk), 900):
                    sub_chunk = chunk[i:i + 1000]
                    if sub_chunk.strip():
                        validated_chunks.append(sub_chunk)
        chunks = validated_chunks
        print(f"[切片] 验证完成，所有 chunk 长度均 <= 1000 字符")

        if not chunks:
            return {
                "success": False,
                "message": "文本切片失败",
                "ids": [],
                "chunks_count": 0
            }

        # 批量插入知识库
        ids = insert_knowledge_batch(chunks, source=filename)
        
        print(f"\n{'='*60}")
        print(f"[上传处理] 文件处理完成: {filename}")
        print(f"[上传处理] 共生成 {len(chunks)} 个知识片段")
        print(f"{'='*60}\n")
        
        return {
            "success": True,
            "message": f"成功插入 {len(chunks)} 个知识片段",
            "ids": ids,
            "chunks_count": len(chunks)
        }
        
    except Exception as e:
        print(f"[上传处理] 错误: {str(e)}")
        return {
            "success": False,
            "message": f"处理失败: {str(e)}",
            "ids": [],
            "chunks_count": 0
        }



