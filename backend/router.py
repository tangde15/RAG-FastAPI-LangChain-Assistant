"""
RAG 路由器：根据知识库相似度分数决定使用知识库还是网络搜索
核心思想：代码控制决策，LLM 只负责回答
"""
from knowledgebase import search_knowledge
from tools import _search_internet_impl
import json


def route_search(query: str, score_threshold_low: float = 0.45, score_threshold_high: float = 0.60, score_threshold_deep: float = 0.55):
    """
    智能搜索路由器：根据知识库相似度分数决定搜索策略
    
    流程：
    1. 第一轮知识库检索（top 3）
    2. 判断最高分数：
       - < 0.45: 直接网络搜索（弱相关）
       - 0.45 ~ 0.60: 第二轮深度检索（中度相关）
       - >= 0.60: 直接使用知识库结果（强相关）
    3. 第二轮判断阈值：>= 0.55 即可使用知识库（因 top_k 扩大后分数略低）
    
    Args:
        query: 用户问题
        score_threshold_low: 低分阈值，低于此分数直接联网（默认 0.45）
        score_threshold_high: 高分阈值，高于此分数直接用知识库（默认 0.60）
        score_threshold_deep: 第二轮阈值，用于深度检索后判断（默认 0.55）
    
    Returns:
        dict: {
            "source": "knowledge" | "web",
            "items": [...],
            "decision_reason": "决策原因说明"
        }
    
    注意：
    - 中文 embedding 相似度通常在 0.45-0.65 之间
    - 0.6+ 已属于强相关，0.7+ 是非常罕见的高度重合
    - 第二轮阈值比第一轮略低是正常的（top_k 增大影响）
    """
    print(f"\n[Router] 开始路由查询: {query}")
    
    # 第一轮：知识库检索（top 3）
    print(f"[Router] 第一轮知识库检索 (top_k=3)...")
    try:
        first_results = search_knowledge(query, top_k=3)
    except Exception as e:
        print(f"[Router] 知识库检索失败: {e}，降级到网络搜索")
        return _fallback_to_web_search(query, "知识库检索失败")
    
    # 如果知识库为空
    if not first_results:
        print(f"[Router] 知识库无结果，降级到网络搜索")
        return _fallback_to_web_search(query, "知识库无结果")
    
    # 提取分数
    scores = []
    for r in first_results:
        s = r.get('score') if isinstance(r, dict) else None
        if s is not None:
            try:
                scores.append(float(s))
            except Exception:
                pass
    
    # 如果没有分数信息
    if not scores:
        print(f"[Router] 无法获取相似度分数，降级到网络搜索")
        return _fallback_to_web_search(query, "无相似度分数")
    
    max_score = max(scores)
    print(f"[Router] 第一轮最高分数: {max_score:.4f}")
    
    # 决策逻辑
    if max_score < score_threshold_low:
        # 低分（< 0.45）→ 网络搜索
        print(f"[Router] 分数 {max_score:.4f} < {score_threshold_low}（弱相关），使用网络搜索")
        return _fallback_to_web_search(query, f"相似度过低 ({max_score:.4f})")
    
    elif max_score >= score_threshold_high:
        # 高分（>= 0.60）→ 直接使用知识库
        print(f"[Router] 分数 {max_score:.4f} >= {score_threshold_high}（强相关），使用知识库结果")
        return _format_knowledge_result(first_results, f"高相似度匹配 ({max_score:.4f})")
    
    else:
        # 中等分数（0.45 ~ 0.60）→ 第二轮深度检索
        print(f"[Router] 分数 {max_score:.4f} 在 [{score_threshold_low}, {score_threshold_high})（中度相关），进行第二轮深度检索 (top_k=10)...")
        try:
            deep_results = search_knowledge(query, top_k=10)
        except Exception as e:
            print(f"[Router] 第二轮检索失败: {e}，使用第一轮结果")
            return _format_knowledge_result(first_results, f"中等相似度，第二轮失败 ({max_score:.4f})")
        
        # 检查第二轮最高分（阈值略低，因为 top_k 增大会影响分数）
        deep_scores = []
        for r in deep_results:
            s = r.get('score') if isinstance(r, dict) else None
            if s is not None:
                try:
                    deep_scores.append(float(s))
                except Exception:
                    pass
        
        if deep_scores:
            max_deep_score = max(deep_scores)
            # 第二轮使用更低的阈值 0.55（因为 top_k=10 扩大后分数分布变化）
            if max_deep_score >= score_threshold_deep:
                print(f"[Router] 第二轮最高分数: {max_deep_score:.4f} >= {score_threshold_deep}（深度检索命中），使用知识库结果")
                return _format_knowledge_result(deep_results, f"深度检索命中 ({max_deep_score:.4f})")
            else:
                print(f"[Router] 第二轮分数 {max_deep_score:.4f} < {score_threshold_deep}（仍不足），降级到网络搜索")
                return _fallback_to_web_search(query, f"深度检索后仍不足 ({max_deep_score:.4f})")
        else:
            # 第二轮无有效分数 → 网络搜索
            print(f"[Router] 第二轮无有效分数，降级到网络搜索")
            return _fallback_to_web_search(query, f"深度检索无有效结果")


def _format_knowledge_result(results, reason):
    """格式化知识库结果"""
    items = []
    for r in results:
        if isinstance(r, dict):
            items.append({
                'title': r.get('source', '知识库条目'),
                'snippet': r.get('content', ''),
                'score': r.get('score'),
                'id': r.get('id')
            })
    
    return {
        "source": "knowledge",
        "items": items,
        "decision_reason": reason
    }


def _fallback_to_web_search(query, reason):
    """降级到网络搜索"""
    print(f"[Router] 执行网络搜索...")
    web_result = _search_internet_impl(query, num=5, with_snippets=True, force_chinese=True)
    
    # web_result 已经是 JSON 字符串，需要解析
    try:
        web_data = json.loads(web_result)
        web_data["decision_reason"] = reason
        return web_data
    except Exception:
        return {
            "source": "web",
            "items": [],
            "decision_reason": reason,
            "error": "网络搜索结果解析失败"
        }
