import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';

interface Props { content: string; }

/**
 * 自动将文本中的 URL 转换为 Markdown 链接格式
 * 例如：https://example.com → [https://example.com](https://example.com)
 * 注意：不处理已经是 Markdown 链接格式的 URL
 */
function autoLinkMarkdown(text: string): string {
  // 先保护已有的 Markdown 链接，避免重复处理
  // 匹配 [任意文本](URL) 格式
  const markdownLinkRegex = /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g;
  const existingLinks: Array<{placeholder: string; original: string}> = [];
  let index = 0;
  
  // 用占位符替换已有的 Markdown 链接
  let protectedText = text.replace(markdownLinkRegex, (match) => {
    const placeholder = `__MDLINK_${index}__`;
    existingLinks.push({placeholder, original: match});
    index++;
    return placeholder;
  });
  
  // 对剩余的裸 URL 进行转换
  // [^\s\)] 表示匹配到空白字符或右括号就停止
  protectedText = protectedText.replace(
    /(https?:\/\/[^\s\)]+)/g,
    url => `[${url}](${url})`
  );
  
  // 还原被保护的 Markdown 链接
  existingLinks.forEach(({placeholder, original}) => {
    protectedText = protectedText.replace(placeholder, original);
  });
  
  return protectedText;
}

const MarkdownMessage: React.FC<Props> = ({ content }) => {
  // 自动转换 URL 为 Markdown 链接
  const processedContent = autoLinkMarkdown(content);
  
  return (
    <div className="markdown-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          code({ inline, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '');
            if (!inline && match) {
              return (
                <pre className={className + ' relative'}>
                  <div style={{position:'absolute',right:8,top:6,fontSize:12,opacity:.6}}>{match[1]}</div>
                  <code {...props}>{children}</code>
                </pre>
              );
            }
            return <code className="bg-gray-700 px-1 py-0.5 rounded text-sm" {...props}>{children}</code>;
          },
          a({ href, children, ...props }) {
            return <a href={href} target="_blank" rel="noopener" {...props}>{children}</a>;
          },
          table({ children, ...props }) {
            return <div style={{overflowX:'auto'}}><table {...props}>{children}</table></div>;
          }
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownMessage;
