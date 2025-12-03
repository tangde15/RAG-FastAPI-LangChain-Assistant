import React, { useState } from 'react';

interface ToolOutputProps {
  content: string;
  toolName?: string;
}

const MAP: Record<string,string> = {
  search_internet:'网络搜索',
  search_knowledge_base:'知识库搜索',
  smart_search:'智能搜索'
};

function tryParse(content: string): any {
  if (!content) return null;
  // 一次解析
  try { return JSON.parse(content); } catch {}
  // 处理双重编码的字符串 "{...}" 或 '\n' 转义
  try {
    const trimmed = content.trim();
    if ((trimmed.startsWith('"') && trimmed.endsWith('"')) || (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
      const unquoted = trimmed.slice(1, -1);
      return JSON.parse(unquoted);
    }
  } catch {}
  return null;
}

function decodeUnicodeEscapes(text: any): any {
  if (typeof text !== 'string') return text;
  try {
    return text.replace(/\\u[0-9a-fA-F]{4}/g, (m) => {
      try {
        const code = parseInt(m.slice(2), 16);
        return String.fromCharCode(code);
      } catch { return m }
    });
  } catch { return text }
}

const ToolOutput: React.FC<ToolOutputProps> = ({ content, toolName='tool' }) => {
  const [open, setOpen] = useState(false);
  const parsed = tryParse(content);
  
  // 优先根据 parsed.source 判断搜索类型
  let displayName = MAP[toolName] || toolName;
  let sourceIcon = '🔍';
  
  if (parsed && typeof parsed === 'object' && parsed.source) {
    if (parsed.source === 'knowledge') {
      displayName = '知识库搜索';
      sourceIcon = '📚';
    } else if (parsed.source === 'web') {
      displayName = '网络搜索';
      sourceIcon = '🌐';
    }
  }

  const renderItems = (items: any[]) => {
    return <div className="space-y-3">{items.slice(0,8).map((raw, i) => {
      const item = typeof raw === 'string' ? { title: raw, snippet: raw } : raw || {};
      const title = decodeUnicodeEscapes(item.title || item.name || item.heading || item.link || `结果${i+1}`);
      const snippet = decodeUnicodeEscapes(item.snippet || item.body || item.description || '');
      const href = item.link || item.href || item.url || '';
      const domain = item.domain || (href || '').replace(/^https?:\/\//, '').split('/')[0];
      return (
        <div key={i} className="rounded-lg p-3 border" style={{ background:'#0f1724', borderColor:'rgba(255,255,255,0.08)', color:'#d7e7ff' }}>
          <div className="flex items-start gap-2">
            <span style={{ color:'#ffd57a', fontWeight:700 }}>#{i+1}</span>
            <h4 className="m-0" style={{ color:'#fff', fontSize:14, fontWeight:600 }}>{title || '无标题'}</h4>
          </div>
          {snippet && <p style={{ fontSize:13, margin:'6px 0 0' }}>{snippet}</p>}
          {href && (
            <div style={{ marginTop:6 }}>
              <a href={href} target="_blank" rel="noopener" style={{ color:'#9ad1ff', fontSize:12, textDecoration:'underline' }}>{domain || href}</a>
            </div>
          )}
        </div>
      );
    })}</div>;
  };

  const render = () => {
    if (!parsed) return <div className="whitespace-pre-wrap break-words text-sm font-mono">{content}</div>;
    // 期望结构 { source, items }
    if (parsed && typeof parsed === 'object' && Array.isArray(parsed.items)) {
      return renderItems(parsed.items);
    }
    if (Array.isArray(parsed)) {
      return renderItems(parsed);
    }
    // 其他对象，回退原始键值显示
    return <div className="p-3 rounded bg-gray-800/50 border border-gray-700/40 text-sm">{Object.entries(parsed).map(([k,v])=> <div key={k}><span className="font-semibold text-yellow-300">{k}:</span> <span>{typeof v === 'object'? JSON.stringify(v): String(v)}</span></div>)}</div>;
  };

  return <div className="my-2">
    <button onClick={()=>setOpen(!open)} className="flex items-center gap-2 text-sm text-yellow-300 hover:text-yellow-200">
      <span style={{display:'inline-block',transform: open? 'rotate(90deg)':'rotate(0deg)',transition:'transform .15s'}}>▶</span>
      <span style={{ fontSize: 16, marginRight: 4 }}>{sourceIcon}</span>
      <span className="font-semibold">{displayName}结果</span>
      <span className="text-xs text-gray-400">{open? '点击收起':'点击展开'}</span>
    </button>
    {open && <div className="ml-4 border-l-2 border-yellow-700/40 pl-3">{render()}</div>}
  </div>;
};

export default ToolOutput;
