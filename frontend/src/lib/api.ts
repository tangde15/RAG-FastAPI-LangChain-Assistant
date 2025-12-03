export interface StreamHandlers {
  onSessionId?: (id:string)=>void;
  onAIChunk?: (chunk:string)=>void;
  onToolOutput?: (output:string, toolName:string)=>void;
  onError?: (e:Error)=>void;
  onComplete?: ()=>void;
}

export async function sendChatMessage(question: string, sessionId: string | null, h: StreamHandlers) {
  const payload: any = sessionId? { question, session_id: sessionId } : { question };
  const resp = await fetch('/api/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
  if (!resp.body) throw new Error('No stream body');
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf='';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, {stream:true});
    const lines = buf.split('\n');
    buf = lines.pop()!;
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const obj = JSON.parse(line);
        switch(obj.type) {
          case 'session': h.onSessionId?.(obj.content); break;
          case 'ai': h.onAIChunk?.(obj.content); break;
          case 'tool_start': break; // could set loading state
          case 'tool': h.onToolOutput?.(obj.content, obj.tool_name || 'tool'); break;
          case 'tool_done': break;
        }
      } catch(e) {
        // ignore parse errors
      }
    }
  }
  if (buf.trim()) {
    try {
      const obj = JSON.parse(buf);
      if (obj.type==='ai') h.onAIChunk?.(obj.content);
    } catch {}
  }
  h.onComplete?.();
}

export async function getAllConversations() {
  const r = await fetch('/api/conversations/all');
  return r.json();
}
export async function getConversationBySession(session_id: string) {
  const r = await fetch('/api/conversations/get', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({session_id}) });
  return r.json();
}
export async function deleteConversation(session_id: string) {
  const r = await fetch('/api/conversations/delete', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({session_id}) });
  return r.json();
}
