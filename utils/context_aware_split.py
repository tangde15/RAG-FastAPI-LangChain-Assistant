def context_aware_split(text, max_len=500, overlap=50):
    """
    聪明的句子切片：按句号/换行优先切，再保证长度 <= max_len（强制范围 500-1000）
    与 BGE 完全兼容，不依赖任何复杂库
    """
    # 强制限制 max_len 在 500-1000 范围内
    max_len = max(500, min(1000, max_len))
    if not text:
        return []
    
    import re

    # 按句子切
    sentences = re.split(r'(?<=[。！？.!?\n])\s*', text)

    chunks = []
    current = ""

    for s in sentences:
        # 如果单个句子超长，强制按 max_len 切分
        if len(s) > max_len:
            # 先添加当前累积的部分
            if current:
                chunks.append(current)
                current = ""
            # 对超长句子进行强制切分
            for i in range(0, len(s), max_len - overlap):
                sub_chunk = s[i:i + max_len]
                if sub_chunk.strip():
                    chunks.append(sub_chunk)
        elif len(current) + len(s) <= max_len:
            current += s
        else:
            if current:
                chunks.append(current)
            current = s

    if current:
        chunks.append(current)

    # 加入 overlap
    final = []
    for i, chk in enumerate(chunks):
        if i == 0:
            final.append(chk)
        else:
            # 确保 overlap 不会导致超长
            overlap_text = chunks[i-1][-overlap:] if len(chunks[i-1]) >= overlap else chunks[i-1]
            combined = overlap_text + chk
            # 如果加上 overlap 后超长，截断
            if len(combined) > max_len:
                final.append(chk[:max_len])
            else:
                final.append(combined)

    return final
