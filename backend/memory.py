from conversations import get_all_conversations, insert_conversation, search_conversations, get_conversations_by_session, delete_conversation_by_session


class Memory:
    def __init__(self):
        # 延迟加载：构造时不要访问 Milvus 或执行可能失败的查询
        self.conversations = {}
        self._loaded = False

    def load(self):
        """从持久层（Milvus / conversations）加载所有对话。"""
        if self._loaded:
            return
        try:
            convs = get_all_conversations()
            # 确保 conversations 是字典（按 session_id 分组）
            self.conversations = convs if convs else {}
            self._loaded = True
        except Exception as e:
            # 记录错误但不要阻止程序启动；后续可重试 load()
            print(f"Memory.load: 无法从持久层加载对话: {e}")
            self.conversations = {}
            self._loaded = False

    def add_conversation(self, conversation: dict, session_id: str):
        """Add a new conversation to memory and persist it."""
        id = insert_conversation(conversation, session_id)
        # 从数据库刷新该 session 的对话数据
        convs = get_conversations_by_session(session_id)
        if convs:
            self.conversations[session_id] = convs

    def get_by_session_id(self, session_id: str):
        """Retrieve conversations for a specific session from DB and update cache."""
        convs = get_conversations_by_session(session_id)
        if convs:
            self.conversations[session_id] = convs
        return convs

    def get_recent_conversations(self, session_id: str, top_k: int = 5):
        """Retrieve recent conversations for a specific session."""
        # 直接从 DB 获取最新数据以避免缓存不一致
        convs = get_conversations_by_session(session_id)
        if convs:
            self.conversations[session_id] = convs
            return convs[-top_k:]
        return []

    def get_related_conversations(self, query: str, session_id: str, top_k: int = 5):
        """Retrieve related conversations based on a query via vector search."""
        return search_conversations(query, session_id=session_id, top_k=top_k)

    def get_all_conversations(self):
        """Return cached conversations; if not loaded attempt to load from DB."""
        if not self._loaded:
            self.load()
        return self.conversations

    def delete_conversation(self, session_id: str):
        """Delete all conversations for a specific session."""
        deleted_count = delete_conversation_by_session(session_id)
        # 从缓存中移除该 session
        if session_id in self.conversations:
            del self.conversations[session_id]
        return deleted_count


global_memory = Memory()  # Singleton instance of Memory



