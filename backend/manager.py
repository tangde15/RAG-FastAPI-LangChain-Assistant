from langchain_community.embeddings import FakeEmbeddings
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv
import os
from pathlib import Path
import httpx

# 使用绝对路径加载配置文件（在项目根目录）
env_path = Path(__file__).parent.parent / "config.env"
load_dotenv(env_path, override=True)

# 初始化 embedding 函数 - 通过远程 API 调用
def get_embedding(texts):
    """
    通过 SiliconFlow API 获取 embedding 向量
    texts: 字符串列表
    返回: 向量列表，每个向量是 1024 维
    """
    api_key = os.getenv("SILICONFLO_API_KEY")
    base_url = os.getenv("SILICONFLO_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("SILICONFLO_EMBEDDING_MODEL", "BAAI/bge-m3")
    
    # 确保 texts 是列表
    if isinstance(texts, str):
        texts = [texts]
    
    # 调用 OpenAI 兼容的 embedding API
    url = f"{base_url}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "input": texts
    }
    
    response = httpx.post(url, headers=headers, json=data, timeout=30.0)
    response.raise_for_status()
    result = response.json()
    
    # 提取向量
    embeddings = [item["embedding"] for item in result["data"]]
    return embeddings

# 创建一个兼容的 embedding_model 对象
class EmbeddingModel:
    def encode(self, texts):
        """
        兼容 FlagEmbedding 的 encode 方法
        返回格式: {'dense_vecs': [[...], [...]]}
        """
        embeddings = get_embedding(texts)
        return {'dense_vecs': embeddings}

embedding_model = EmbeddingModel()

# 初始化 embedding 函数
fakeEmbeddings = FakeEmbeddings(size=1024)

# 初始化聊天模型
deepseek_chat = init_chat_model(
    model="deepseek-chat",
    openai_api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url=os.environ.get('DEEPSEEK_BASE_URL'),
)

from pymilvus import MilvusClient

MILVUS_HOST = os.getenv("MILVUS_HOST")
MILVUS_PORT = os.getenv("MILVUS_PORT")
MILVUS_DB_NAME = os.getenv("MILVUS_DATABASE")

# 初始化 Milvus 客户端
milvus_client = MilvusClient(
    host = MILVUS_HOST,
    port = MILVUS_PORT,
    db_name = MILVUS_DB_NAME
)
