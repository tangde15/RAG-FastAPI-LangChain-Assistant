"""
文件解析模块：支持 PDF、DOCX、PPTX、TXT 等格式
"""
import os
from typing import List

def read_pdf(path: str) -> str:
    """解析 PDF 文件"""
    try:
        import pdfplumber
        print(f"[文件解析] 开始解析 PDF 文件: {os.path.basename(path)}")
        text = []
        with pdfplumber.open(path) as pdf:
            total_pages = len(pdf.pages)
            print(f"[文件解析] PDF 共 {total_pages} 页")
            for i, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
                    print(f"[文件解析] 已解析第 {i}/{total_pages} 页")
        result = "\n".join(text)
        print(f"[文件解析] PDF 解析完成，提取文本 {len(result)} 字符")
        return result
    except ImportError:
        raise ImportError("请安装 pdfplumber: pip install pdfplumber")
    except Exception as e:
        raise Exception(f"PDF 解析失败: {str(e)}")


def read_docx(path: str) -> str:
    """解析 Word 文件"""
    try:
        import docx
        print(f"[文件解析] 开始解析 Word 文件: {os.path.basename(path)}")
        doc = docx.Document(path)
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        result = "\n".join(paragraphs)
        print(f"[文件解析] Word 解析完成，提取 {len(paragraphs)} 个段落，共 {len(result)} 字符")
        return result
    except ImportError:
        raise ImportError("请安装 python-docx: pip install python-docx")
    except Exception as e:
        raise Exception(f"DOCX 解析失败: {str(e)}")


def read_pptx(path: str) -> str:
    """解析 PowerPoint 文件"""
    try:
        from pptx import Presentation
        print(f"[文件解析] 开始解析 PowerPoint 文件: {os.path.basename(path)}")
        prs = Presentation(path)
        texts = []
        total_slides = len(prs.slides)
        print(f"[文件解析] PPT 共 {total_slides} 页")
        for i, slide in enumerate(prs.slides, 1):
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    texts.append(shape.text.strip())
            print(f"[文件解析] 已解析第 {i}/{total_slides} 页")
        result = "\n".join(texts)
        print(f"[文件解析] PPT 解析完成，提取文本 {len(result)} 字符")
        return result
    except ImportError:
        raise ImportError("请安装 python-pptx: pip install python-pptx")
    except Exception as e:
        raise Exception(f"PPTX 解析失败: {str(e)}")


def read_txt(path: str) -> str:
    """解析文本文件"""
    try:
        print(f"[文件解析] 开始解析文本文件: {os.path.basename(path)}")
        with open(path, "r", encoding="utf-8") as f:
            result = f.read()
        print(f"[文件解析] 文本文件解析完成，共 {len(result)} 字符")
        return result
    except UnicodeDecodeError:
        # 尝试其他编码
        try:
            print(f"[文件解析] UTF-8 编码失败，尝试 GBK 编码")
            with open(path, "r", encoding="gbk") as f:
                result = f.read()
            print(f"[文件解析] 文本文件解析完成（GBK），共 {len(result)} 字符")
            return result
        except Exception:
            print(f"[文件解析] GBK 编码失败，尝试 Latin-1 编码")
            with open(path, "r", encoding="latin-1") as f:
                result = f.read()
            print(f"[文件解析] 文本文件解析完成（Latin-1），共 {len(result)} 字符")
            return result
    except Exception as e:
        raise Exception(f"TXT 解析失败: {str(e)}")


def read_file(path: str) -> str:
    """
    根据文件扩展名自动选择解析器
    支持: .pdf, .docx, .pptx, .txt, .md
    """
    ext = os.path.splitext(path)[1].lower()
    
    if ext == '.pdf':
        return read_pdf(path)
    elif ext == '.docx':
        return read_docx(path)
    elif ext == '.pptx':
        return read_pptx(path)
    elif ext in ['.txt', '.md']:
        return read_txt(path)
    else:
        raise ValueError(f"不支持的文件类型: {ext}")


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """
    将长文本切分成多个片段（chunking）
    
    Args:
        text: 原始文本
        chunk_size: 每个片段的最大字符数
        overlap: 片段之间的重叠字符数
    
    Returns:
        文本片段列表
    """
    if not text or not text.strip():
        return []
    
    print(f"[文本切片] 开始切片，文本长度: {len(text)} 字符")
    print(f"[文本切片] 切片大小: {chunk_size} 字符，重叠: {overlap} 字符")
    
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        
        if chunk:  # 只添加非空片段
            chunks.append(chunk)
            print(f"[文本切片] 已生成第 {len(chunks)} 个片段 ({len(chunk)} 字符)")
        
        # 如果已经到达末尾，退出
        if end >= text_len:
            break
            
        start = end - overlap
        
        # 避免无限循环
        if start <= 0:
            start = end
    
    print(f"[文本切片] 切片完成，共生成 {len(chunks)} 个片段")
    return chunks


# 支持的文件类型
SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.pptx', '.txt', '.md'}


def is_supported_file(filename: str) -> bool:
    """检查文件是否支持"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in SUPPORTED_EXTENSIONS
