from pymilvus import DataType
import json
from manager import milvus_client, embedding_model
from uuid import uuid4

def create_conversations():
    if milvus_client.has_collection("conversations"):
        print("Collection 'conversations' already exists.")
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
        field_name="session_id",
        datatype=DataType.VARCHAR,
        max_length=800
    )
    schema.add_field(
        field_name="content", 
        datatype=DataType.JSON,
    )
    schema.add_field(
        field_name="dense_vector", 
        datatype=DataType.FLOAT_VECTOR, 
        # dim 指定向量维度
        dim=1024
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

    index_params.add_index(
        field_name="session_id",
        index_type="AUTOINDEX"
    )

    index_params.add_index(
        field_name="timestamp",
        index_type="AUTOINDEX"
    )

    # 创建集合
    milvus_client.create_collection(
        collection_name="conversations",
        schema=schema,
        index_params=index_params
    )

    res = milvus_client.get_load_state(
        collection_name="conversations"
    )

    print(res)


def insert_conversation(conversation: dict, session_id: str):
    """
    插入一条对话记录
    Args:
        conversation: 对话内容，格式为 {"user_message": "...", "ai_message": "..."}
        session_id: 会话ID
    """
    # 将对话字典转换为字符串用于编码
    conversation_text = json.dumps(conversation, ensure_ascii=False)
    vector = embedding_model.encode([conversation_text])['dense_vecs'][0]
    
    from datetime import datetime

    now = datetime.now()
    timestamp = now.timestamp()

    res = milvus_client.insert(
        collection_name="conversations",
        data=[{
            "session_id": session_id,
            "content": conversation,
            "dense_vector": vector,
            "timestamp": timestamp
        }]
    )

    print(f"Inserted conversation, ID: {res['ids'][0]}")

    return res['ids'][0]


def insert_conversations(conversations: list, session_id: str):
    ids = []
    for conversation in conversations:
        id = insert_conversation(conversation, session_id=session_id)
        ids.append(id)
    return ids


def search_conversations(query: str, session_id: str, top_k: int = 5):
    query_vector = embedding_model.encode([query])['dense_vecs'][0]
    # 使用范围搜索
    # 默认度量类型COSINE
    res = milvus_client.search(
        collection_name="conversations",
        data=[query_vector],
        limit=top_k,
        # search_params={
        #     "params": {
        #         "radius": 0.49,
        #         "range_filter": 0.99
        #     }
        # },
        filter=f'session_id == "{session_id}"'
    )

    data = []
    # {'content': {'user_message': 'Hello, how are you?', 'ai_message': "I'm fine, thank you!"}, 'id': '462014062345986300'}
    for hits in res:
        # print("TopK results:")
        for hit in hits:
            entity = milvus_client.get(
                collection_name="conversations",
                ids=[hit['id']],
                output_fields=["content"]
            )
            # print(entity[0])
            data.append(entity[0])

    return data


def get_recent_conversations(session_id: str, top_k: int = 5):
    """
    获取指定会话中时间戳最新的 k 条对话记录
    
    Args:
        session_id: 会话ID
        k: 返回的对话记录数量，默认为5
        
    Returns:
        list: 按时间戳降序排列的对话记录列表
    """
    res = milvus_client.query(
        collection_name="conversations",
        filter=f'session_id == "{session_id}"',
        output_fields=["id", "content", "timestamp"],
    )
    
    # 按时间戳降序排序
    sorted_conversations = sorted(res, key=lambda x: x['timestamp'], reverse=True)

    # 只返回前 top_k 条
    return sorted_conversations[:top_k]


def get_all_conversations():
    """
    获取所有对话记录，按 session_id 分组
    
    Returns:
        dict: 按 session_id 分组的对话记录字典，格式为 {session_id: [conversation1, conversation2, ...]}
    """

    # {'3a873d98-169d-4539-aebd-b24315a9edf9': [{'id': '462014062345986299', 'content': {'user_message': 'Hello, how are you?', 'ai_message': "I'm fine, thank you!"}, 'timestamp': 1763277317.066648}], ...}

    res = milvus_client.query(
        collection_name="conversations",
        filter="",  # 空过滤器
        output_fields=["id", "content", "session_id", "timestamp"],
        # 不使用 filter 参数或使用空 filter 时，必须指定 limit
        limit=16384  # Milvus 默认最大限制
    )
    # res 为一个 HybridExtraList 对象，可以看作一个普通的列表
    
    # 按 session_id 分组
    grouped_conversations = {}
    for item in res:
        session_id = item['session_id']
        if session_id not in grouped_conversations:
            grouped_conversations[session_id] = []
        grouped_conversations[session_id].append({
            'id': item['id'],
            'content': item['content'],
            'timestamp': item['timestamp']
        })
    
    # 对每个 session 内的对话按时间戳排序
    for session_id in grouped_conversations:
        grouped_conversations[session_id].sort(key=lambda x: x['timestamp'])
    
    return grouped_conversations


def get_conversations_by_session(session_id: str):
    """
    获取指定会话的所有对话记录
    
    Args:
        session_id: 会话ID
        
    Returns:
        list: 该会话的所有对话记录列表，按时间戳升序排列
    """

    # [{'id': '462014062345986300', 'content': {'user_message': 'Hello, how are you?', 'ai_message': "I'm fine, thank you!"}, 'timestamp': 1763277551.109031}, ...]

    res = milvus_client.query(
        collection_name="conversations",
        filter=f'session_id == "{session_id}"',
        output_fields=["id", "content", "timestamp"],
    )
    
    # 按时间戳升序排序
    sorted_conversations = sorted(res, key=lambda x: x['timestamp'])
    
    return sorted_conversations


def delete_conversation_by_session(session_id: str):
    """
    删除指定会话的所有对话记录
    
    Args:
        session_id: 会话ID
        
    Returns:
        int: 删除的记录数量
    """
    # 先查询该 session_id 下的所有记录 ID
    res = milvus_client.query(
        collection_name="conversations",
        filter=f'session_id == "{session_id}"',
        output_fields=["id"],
    )
    
    if not res:
        return 0
    
    # 提取所有 ID
    ids = [item['id'] for item in res]
    
    # 批量删除
    milvus_client.delete(
        collection_name="conversations",
        ids=ids
    )
    
    print(f"Deleted {len(ids)} conversations for session {session_id}")
    return len(ids)




