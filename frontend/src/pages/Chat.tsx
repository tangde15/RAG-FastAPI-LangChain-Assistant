import React, { useEffect, useRef, useState } from 'react';
import MarkdownMessage from '../components/MarkdownMessage';
import ToolOutput from '../components/ToolOutput';
import UploadModal from '../components/UploadModal';
import { sendChatMessage, getAllConversations, getConversationBySession, deleteConversation } from '../lib/api';

interface Message { type:'user'|'ai'; content:string; timestamp:number; toolCalls?: {toolName:string; toolOutput:string; insertPosition:number}[] }
interface ConversationItem { session_id:string; user_message:string; ai_message:string; timestamp?: number }

const Chat: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string|null>(null);
  const [allConvs, setAllConvs] = useState<ConversationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const processingRef = useRef(false);
  const aiBufferRef = useRef('');
  const endRef = useRef<HTMLDivElement|null>(null);

  const scrollBottom = () => { endRef.current?.scrollIntoView({behavior:'smooth'}); };
  useEffect(scrollBottom, [messages]);

  async function loadAll() {
    try {
      const data = await getAllConversations();
      setAllConvs(data.conversations||[]);
    } catch(e) { console.error(e); }
  }
  useEffect(()=>{ loadAll(); }, []);

  async function loadSession(sid:string) {
    try {
      const data = await getConversationBySession(sid);
      const msgs: Message[] = [];
      (data.conversations||[]).forEach((c:ConversationItem)=>{
        msgs.push({ type:'user', content:c.user_message, timestamp: Date.now() });
        msgs.push({ type:'ai', content:c.ai_message, timestamp: Date.now(), toolCalls: [] });
      });
      setMessages(msgs);
      setSessionId(sid);
    } catch(e) { console.error(e); }
  }

  function startNew() {
    setMessages([]); setSessionId(null); aiBufferRef.current=''; processingRef.current=false; 
    // 刷新历史列表，将当前对话加入历史
    loadAll();
  }

  async function handleDelete(sid: string, e: React.MouseEvent) {
    e.stopPropagation(); // 防止触发加载对话
    if (!confirm('确定要删除这个对话吗？')) return;
    try {
      await deleteConversation(sid);
      // 如果删除的是当前对话，清空界面
      if (sid === sessionId) {
        startNew();
      } else {
        // 否则只刷新列表
        loadAll();
      }
    } catch(e) {
      console.error('删除失败:', e);
      alert('删除失败，请重试');
    }
  }

  async function handleSend() {
    const q = input.trim();
    if (!q || loading || processingRef.current) return;
    processingRef.current = true;
    setLoading(true);
    setMessages(m=> [...m, {type:'user', content:q, timestamp: Date.now()}, {type:'ai', content:'', timestamp: Date.now(), toolCalls:[]}]);
    aiBufferRef.current='';
    setInput('');
    try {
      await sendChatMessage(q, sessionId, {
        onSessionId: (id)=> setSessionId(id),
        onAIChunk: (chunk)=> {
          aiBufferRef.current += chunk;
          setMessages((m: Message[])=> {
            const arr=[...m];
            const last= arr[arr.length-1];
            if (last?.type==='ai') last.content = aiBufferRef.current;
            return arr;
          });
        },
        onToolOutput: (output, toolName)=> {
          const pos = aiBufferRef.current.length;
          setMessages((m: Message[])=> {
            const arr=[...m];
            const last= arr[arr.length-1];
            if (last?.type==='ai') {
              last.toolCalls = last.toolCalls || [];
              last.toolCalls.push({ toolName, toolOutput: output, insertPosition: pos });
            }
            return arr;
          });
        },
        onComplete: ()=> { setLoading(false); processingRef.current=false; aiBufferRef.current=''; loadAll(); },
        onError: (e)=> { console.error(e); setLoading(false); processingRef.current=false; }
      });
    } catch(e) {
      console.error(e);
      setLoading(false);
      processingRef.current=false;
    }
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  }

  const uniqueSessions = (()=> {
    const map = new Map<string, ConversationItem>();
    // 去重：每个 session_id 只保留一条记录
    for (const c of allConvs) if (!map.has(c.session_id)) map.set(c.session_id, c);
    // 转换为数组并按时间戳倒序排序（最新的在最上面）
    return Array.from(map.values()).sort((a, b) => {
      const timeA = a.timestamp || 0;
      const timeB = b.timestamp || 0;
      return timeB - timeA; // 倒序：新的在前
    });
  })();

  return (
    <div style={{display:'flex', height:'100vh', background:'#0f172a'}}>
      {/* Sidebar */}
      <div style={{width:280, background:'#1e293b', borderRight:'1px solid #334155', display:'flex', flexDirection:'column'}}>
        <div style={{padding:16, borderBottom:'1px solid #334155'}}>
          <button onClick={startNew} style={{width:'100%', padding:'12px 14px', background:'#2563eb', color:'#fff', border:'none', borderRadius:8, fontWeight:600, cursor:'pointer'}}>+ 新建对话</button>
        </div>
        <div style={{flex:1, overflowY:'auto', padding:16}} className="scrollbar">
          <h3 style={{fontSize:12, color:'#94a3b8', margin:'0 0 8px 4px'}}>对话历史</h3>
          {uniqueSessions.length===0 && <div style={{color:'#64748b', fontSize:12, padding:'24px 0'}}>暂无记录</div>}
          <div style={{display:'flex', flexDirection:'column', gap:8}}>
            {uniqueSessions.map(s=> {
              const active = s.session_id === sessionId;
              return <div key={s.session_id} style={{position:'relative'}}>
                <button 
                  onClick={()=>loadSession(s.session_id)} 
                  style={{
                    width:'100%',
                    textAlign:'left', 
                    padding:'10px 12px', 
                    paddingRight: '36px', // 为删除按钮留出空间
                    borderRadius:8, 
                    background: active? '#334155':'#1e293b', 
                    color: active? '#fff':'#cbd5e1', 
                    border:'1px solid #334155', 
                    cursor:'pointer'
                  }}
                >
                  <div style={{fontSize:13, fontWeight:500, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis'}}>{s.user_message}</div>
                  <div style={{fontSize:11, color:'#64748b', marginTop:4}}>{s.session_id.slice(0,8)}...</div>
                </button>
                <button
                  onClick={(e) => handleDelete(s.session_id, e)}
                  style={{
                    position:'absolute',
                    right: 8,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    padding: '6px 8px',
                    background: 'transparent',
                    border: 'none',
                    color: '#64748b',
                    cursor: 'pointer',
                    fontSize: 16,
                    lineHeight: 1,
                    transition: 'color 0.2s'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.color = '#ef4444'}
                  onMouseLeave={(e) => e.currentTarget.style.color = '#64748b'}
                  title="删除对话"
                >
                  🗑️
                </button>
              </div>
            })}
          </div>
        </div>
        <div style={{padding:16, borderTop:'1px solid #334155'}}>
          <button 
            onClick={() => setUploadModalOpen(true)}
            style={{
              display:'block', 
              width:'100%', 
              textAlign:'center', 
              padding:'10px 12px', 
              background:'#334155', 
              color:'#e2e8f0', 
              border: 'none',
              borderRadius:8, 
              fontSize:13, 
              cursor: 'pointer',
              textDecoration:'none'
            }}
          >
            📤 上传文档
          </button>
        </div>
      </div>
      {/* Main */}
      <div style={{flex:1, display:'flex', flexDirection:'column'}}>
        <div style={{padding:'14px 20px', borderBottom:'1px solid #334155', background:'#1e293b', display:'flex', justifyContent:'space-between', alignItems:'center'}}>
          <div style={{display:'flex', alignItems:'center', gap:12}}>
            <h1 style={{margin:0, fontSize:20, fontWeight:600}}>AI Assistant</h1>
            {sessionId && <span style={{fontSize:12, color:'#64748b'}}>Session: {sessionId.slice(0,8)}...</span>}
          </div>
          <button onClick={loadAll} style={{padding:'8px 14px', background:'#334155', color:'#e2e8f0', border:'none', borderRadius:8, fontSize:13, cursor:'pointer'}}>🔄 刷新</button>
        </div>
        <div style={{flex:1, overflowY:'auto', padding:'24px 32px'}} className="scrollbar">
          <div style={{maxWidth:960, margin:'0 auto', display:'flex', flexDirection:'column', gap:24}}>
            {messages.length===0 && <div style={{textAlign:'center', marginTop:80, color:'#64748b'}}><div style={{fontSize:56}}>💬</div><h2 style={{margin:'12px 0 4px', fontSize:24}}>开始新对话</h2><p style={{fontSize:12}}>输入你的问题，我会尽力帮助你</p></div>}
            {messages.map((m,i)=> {
              const isUser = m.type==='user';
              return <div key={i} style={{display:'flex', justifyContent: isUser? 'flex-end':'flex-start'}}>
                <div style={{maxWidth:880, background: isUser? '#2563eb':'#1e293b', color: isUser? '#fff':'#e2e8f0', padding:'12px 16px', borderRadius:18, fontSize:14}}>
                  {isUser? <div style={{whiteSpace:'pre-wrap'}}>{m.content}</div>: (
                    <>{(() => {
                      if (!m.toolCalls || m.toolCalls.length===0) return <MarkdownMessage content={m.content}/>;
                      const sorted = [...m.toolCalls].sort((a,b)=> a.insertPosition - b.insertPosition);
                      const segments: JSX.Element[] = [];
                      let last = 0;
                      for (let idx=0; idx<sorted.length; idx++) {
                        const call = sorted[idx];
                        if (call.insertPosition > last) {
                          const seg = m.content.substring(last, call.insertPosition);
                          if (seg.trim()) segments.push(<MarkdownMessage key={'seg-'+idx} content={seg} />);
                        }
                        segments.push(<ToolOutput key={'tool-'+idx} content={call.toolOutput} toolName={call.toolName} />);
                        last = call.insertPosition;
                      }
                      if (last < m.content.length) {
                        const tail = m.content.substring(last);
                        if (tail.trim()) segments.push(<MarkdownMessage key={'tail'} content={tail} />);
                      }
                      return segments;
                    })()}</>
                  )}
                </div>
              </div>;
            })}
            <div ref={endRef} />
          </div>
        </div>
        <div style={{padding:'16px 24px', borderTop:'1px solid #334155', background:'#1e293b'}}>
          <div style={{maxWidth:960, margin:'0 auto', display:'flex', gap:12, alignItems:'flex-end'}}>
            <div style={{flex:1, background:'#334155', padding:'10px 14px', borderRadius:20}}>
              <textarea value={input} onChange={e=> setInput(e.target.value)} onKeyDown={handleKey} placeholder="输入消息... (Enter 发送)" rows={1} style={{width:'100%', background:'transparent', resize:'none', outline:'none', color:'#e2e8f0', fontSize:14}} />
            </div>
            <button disabled={loading || !input.trim()} onClick={handleSend} style={{padding:'12px 24px', background: loading? '#475569':'#2563eb', color:'#fff', border:'none', borderRadius:24, fontWeight:500, cursor: loading? 'not-allowed':'pointer'}}>{loading? '发送中':'发送'}</button>
          </div>
          <div style={{textAlign:'center', marginTop:8, fontSize:11, color:'#64748b'}}>AI 可能会产生不准确的信息，请核实重要内容。</div>
        </div>
      </div>

      {/* 上传文档 Modal */}
      <UploadModal 
        isOpen={uploadModalOpen} 
        onClose={() => setUploadModalOpen(false)}
        onUploadSuccess={() => {
          // 上传成功后可以刷新对话列表或显示提示
          loadAll();
        }}
      />
    </div>
  );
};

export default Chat;
