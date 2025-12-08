from langchain.tools import tool
import logging
import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse
import re
from knowledgebase import search_knowledge

@tool("_extract_snippet")
def _extract_snippet(html: str) -> str:
    """从页面 HTML 提取摘要：优先 meta/og/twitter 描述，其次首段落。"""
    try:
        soup = BeautifulSoup(html, 'html.parser')
        # 1) 标准 meta description
        meta = soup.find('meta', attrs={'name': re.compile('description', re.I)})
        if meta and meta.get('content'):
            desc = meta.get('content', '').strip()
            if desc:
                return desc[:300]
        # 2) Open Graph 描述
        og = soup.find('meta', attrs={'property': re.compile('og:description', re.I)})
        if og and og.get('content'):
            desc = og.get('content', '').strip()
            if desc:
                return desc[:300]
        # 3) Twitter 描述
        tw = soup.find('meta', attrs={'name': re.compile('twitter:description', re.I)})
        if tw and tw.get('content'):
            desc = tw.get('content', '').strip()
            if desc:
                return desc[:300]
        # 4) 优先从 <article> 区域提取正文段落
        try:
            article = soup.find('article')
            if article:
                for p in article.find_all('p'):
                    text = (p.get_text(" ", strip=True) or '').strip()
                    if not text:
                        continue
                    if re.search(r'(导航|版权|免责声明|Cookie|隐私|登录|注册)', text):
                        continue
                    if 40 <= len(text) <= 600:
                        return text[:300]
        except Exception:
            pass

        # 5) 针对维基百科抓取正文区域首段
        try:
            content = soup.select_one('#mw-content-text .mw-parser-output') or soup.select_one('#mw-content-text')
            if content:
                for p in content.find_all('p', recursive=False):
                    text = (p.get_text(" ", strip=True) or '').strip()
                    if text and len(text) >= 40:
                        return text[:300]
        except Exception:
            pass

        # 6) 首个足够长的段落，排除导航/版权等弱文本
        for p in soup.find_all('p'):
            text = (p.get_text(" ", strip=True) or '').strip()
            # 过滤包含“版权”“导航”“免责声明”等低质量段落关键词
            if not text:
                continue
            low_quality = re.search(r'(导航|版权|免责声明|Cookie|隐私|登录|注册)', text)
            if low_quality:
                continue
            # 选择长度合适的正文段落
            if 40 <= len(text) <= 600:
                return text[:300]
    except Exception:
        pass
    return ''

def _rewrite_queries(query: str) -> list[str]:
    """生成 3-5 条重写查询：加入中文语言提示与同义变体。"""
    q = (query or '').strip()
    base = [q]
    # 中文语言提示变体
    hints = [
        f"{q} 中文",
        f"{q} 资料",
        f"{q} 问题解答",
        f"{q} 教程",
    ]
    # 同义表达（极简启发式）
    syn = []
    if len(q) <= 64:
        syn.append(f"{q} 是什么")
        syn.append(f"{q} 如何解决")
    out = []
    for s in (base + hints + syn):
        if s and s not in out:
            out.append(s)
    return out[:5]

def _search_ddg(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo HTML 搜索（国内更稳定），返回基本结果。"""
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    }
    try:
        resp = requests.post(url, data={"q": query}, headers=headers, timeout=10)
    except Exception:
        return []
    soup = BeautifulSoup(resp.text, 'html.parser')
    items = []
    for r in soup.select('a.result__a'):
        title = r.get_text(strip=True)
        link = r.get('href', '').strip()
        if not link:
            continue
        domain = ''
        try:
            domain = urlparse(link).netloc
        except Exception:
            domain = ''
        items.append({
            'title': title,
            'link': link,
            'domain': domain,
        })
        if len(items) >= max_results:
            break
    return items

def _fetch_and_summarize(link: str, headers: dict) -> str:
    """抓取页面并提取摘要。"""
    try:
        r = requests.get(link, headers=headers, timeout=8)
        if r.status_code == 200 and 'text/html' in r.headers.get('Content-Type',''):
            return _extract_snippet(r.text)
    except Exception:
        return ''
    return ''

def _is_chinese_text(text: str) -> bool:
    """简单中文检测：统计 CJK 字符数量与占比。"""
    if not text:
        return False
    try:
        chars = re.findall(r"[\u4e00-\u9fff]", text)
        return len(chars) >= 8 and (len(chars) / max(len(text), 1)) >= 0.05
    except Exception:
        return False

def _rerank(query: str, items: list[dict]) -> list[dict]:
    """简易 rerank：中文优先、词匹配、标题长度适中。"""
    q_tokens = [t for t in re.split(r"\s+", query.strip()) if t]
    def score(it: dict) -> float:
        title = it.get('title','')
        snippet = it.get('snippet','')
        s = 0.0
        # 中文优先
        if _is_chinese_text(title) or _is_chinese_text(snippet):
            s += 2.0
        # 词匹配（粗略）
        for t in q_tokens:
            if t and (t in title or t in snippet):
                s += 0.8
        # 标题长度适中
        l = len(title)
        if 8 <= l <= 80:
            s += 0.5
        return s
    return sorted(items, key=score, reverse=True)

def _is_chinese_text(text: str) -> bool:
    """简单中文检测：统计 CJK 字符数量与占比。"""
    if not text:
        return False
    try:
        chars = re.findall(r"[\u4e00-\u9fff]", text)
        return len(chars) >= 8 and (len(chars) / max(len(text), 1)) >= 0.05
    except Exception:
        return False


def _search_internet_impl(query: str, num: int = 5, with_snippets: bool = True, force_chinese: bool = True) -> str:
    """内部实现：使用必应中国搜索并返回结构化结果。供工具和内部调用。
    force_chinese: 为 True 时尽量保证返回中文结果（首选中文市场、语言头，并对结果进行中文过滤）。
    """
    log = logging.getLogger('custom.tools')
    log.info('search_internet called', extra={'query_len': len(query or ''), 'num': num, 'with_snippets': with_snippets})
    url = "https://cn.bing.com/search"
    params = {"q": query, "mkt": "zh-CN", "setlang": "zh-Hans"}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    }
    try:
        # 1) Query 重写
        qlist = _rewrite_queries(query)
        agg: list[dict] = []
        # 2) 多轮 DDG 搜索
        for q in qlist:
            ddg_items = _search_ddg(q, max_results=max(3, num))
            agg.extend(ddg_items)
        # 去重（按链接）
        seen = set()
        unique = []
        for it in agg:
            link = it.get('link','')
            if link and link not in seen:
                unique.append(it)
                seen.add(link)
        # 3) 抓取正文 + 摘要
        items = []
        for it in unique[: max(10, num*2)]:
            link = it.get('link','')
            snippet = _fetch_and_summarize(link, headers=headers) if with_snippets else ''
            # 4) 中文过滤（可选）
            if force_chinese:
                if not (_is_chinese_text(it.get('title','')) or _is_chinese_text(snippet)):
                    # 低成本再判：直接以摘要为准，摘要无中文则跳过
                    continue
            items.append({
                'title': it.get('title',''),
                'link': link,
                'snippet': snippet,
                'domain': it.get('domain',''),
            })
        # 5) 简易 rerank
        items = _rerank(query, items)[:num]
        log.info('search_ddg finished', extra={'found': len(items)})
        return json.dumps({"source": "web", "items": items}, ensure_ascii=False)
    except Exception as e:
        log.exception('ddg pipeline failed')
        return json.dumps({"source": "web", "error": str(e), "items": []}, ensure_ascii=False)

@tool("search_internet")
def search_internet(query: str, num: int = 5, with_snippets: bool = True, force_chinese: bool = True) -> str:
    """工具包装：转发到内部实现。"""
    return _search_internet_impl(query, num=num, with_snippets=with_snippets, force_chinese=force_chinese)


@tool("search_knowledge_base")
def search_knowledge_base(query: str) -> str:
    """知识库搜索，返回统一的 {source: 'knowledge', items: [...]} 格式。"""
    try:
        results = search_knowledge(query, top_k=5)
        # 转换为统一格式，让前端能正常渲染
        items = []
        for r in results:
            if isinstance(r, dict):
                items.append({
                    'title': r.get('source', '知识库条目'),
                    'snippet': r.get('content', ''),
                    'score': r.get('score'),
                    'id': r.get('id')
                })
        return json.dumps({"source": "knowledge", "items": items}, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"source": "knowledge", "error": str(e), "items": []}, ensure_ascii=False)


@tool("smart_search")
def smart_search(query: str) -> str:
    """智能搜索工具：自动路由到知识库或网络搜索。
    
    决策由代码控制，而非 LLM 决定：
    - 相似度 < 0.45: 网络搜索（弱相关）
    - 相似度 0.45-0.60: 深度检索后决定
    - 相似度 >= 0.60: 使用知识库（强相关）
    
    不需要 LLM 判断是否搜索，系统自动决策。
    """
    from router import route_search
    
    # 使用 Router 自动决策（使用默认阈值：low=0.45, high=0.60, deep=0.55）
    result = route_search(query)
    
    # 打印决策结果（调试用）
    print(f"[smart_search] 决策结果: source={result.get('source')}, reason={result.get('decision_reason')}")
    
    # 返回 JSON 字符串
    return json.dumps(result, ensure_ascii=False, default=str)


