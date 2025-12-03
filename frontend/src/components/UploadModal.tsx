import React, { useState, useRef } from 'react';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: () => void;
}

interface UploadStatus {
  state: 'idle' | 'uploading' | 'success' | 'error';
  fileName?: string;
  fileSize?: number;
  chunksCount?: number;
  message?: string;
  progress?: number;
}

const UploadModal: React.FC<UploadModalProps> = ({ isOpen, onClose, onUploadSuccess }) => {
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>({ state: 'idle' });
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileSelect = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 验证文件类型
    const validExtensions = ['.pdf', '.docx', '.pptx', '.txt', '.md'];
    const fileExt = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!validExtensions.includes(fileExt)) {
      setUploadStatus({
        state: 'error',
        message: '不支持的文件格式，仅支持 PDF、Word、Excel、PowerPoint、文本、Markdown 格式'
      });
      return;
    }

    // 验证文件大小（20MB）
    if (file.size > 20 * 1024 * 1024) {
      setUploadStatus({
        state: 'error',
        message: '文件大小超过 20MB 限制'
      });
      return;
    }

    // 开始上传
    setUploadStatus({
      state: 'uploading',
      fileName: file.name,
      fileSize: file.size,
      progress: 0
    });

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('http://localhost:8000/api/knowledge/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '上传失败');
      }

      const result = await response.json();
      
      setUploadStatus({
        state: 'success',
        fileName: file.name,
        fileSize: file.size,
        chunksCount: result.chunks_count,
        message: result.message
      });

      // 3秒后自动关闭并刷新
      setTimeout(() => {
        onUploadSuccess();
        handleClose();
      }, 3000);

    } catch (error: any) {
      setUploadStatus({
        state: 'error',
        fileName: file.name,
        message: error.message || '上传失败，请重试'
      });
    }

    // 重置 input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleClose = () => {
    setUploadStatus({ state: 'idle' });
    onClose();
  };

  const handleRetry = () => {
    setUploadStatus({ state: 'idle' });
  };

  return (
    <div 
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.75)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        backdropFilter: 'blur(4px)'
      }}
      onClick={handleClose}
    >
      <div 
        style={{
          background: '#1e293b',
          borderRadius: 16,
          padding: 32,
          maxWidth: 600,
          width: '90%',
          border: '1px solid #334155',
          boxShadow: '0 20px 50px rgba(0, 0, 0, 0.5)'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#f1f5f9' }}>上传文档到知识库</h2>
          <button 
            onClick={handleClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              fontSize: 24,
              cursor: 'pointer',
              padding: 0,
              lineHeight: 1
            }}
          >
            ×
          </button>
        </div>

        {/* 上传状态：空闲 */}
        {uploadStatus.state === 'idle' && (
          <>
            <div 
              style={{
                border: '2px dashed #475569',
                borderRadius: 12,
                padding: 48,
                textAlign: 'center',
                background: '#0f172a',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
              onClick={handleFileSelect}
              onDragOver={(e) => {
                e.preventDefault();
                e.currentTarget.style.borderColor = '#2563eb';
              }}
              onDragLeave={(e) => {
                e.currentTarget.style.borderColor = '#475569';
              }}
              onDrop={(e) => {
                e.preventDefault();
                e.currentTarget.style.borderColor = '#475569';
                const file = e.dataTransfer.files?.[0];
                if (file && fileInputRef.current) {
                  const dt = new DataTransfer();
                  dt.items.add(file);
                  fileInputRef.current.files = dt.files;
                  fileInputRef.current.dispatchEvent(new Event('change', { bubbles: true }));
                }
              }}
            >
              <div style={{ fontSize: 64, marginBottom: 16 }}>📁</div>
              <h3 style={{ margin: '0 0 12px', fontSize: 18, color: '#f1f5f9' }}>拖拽文件到这里上传</h3>
              <p style={{ margin: '0 0 20px', fontSize: 14, color: '#94a3b8' }}>
                支持 PDF、Word、Excel、PowerPoint、文本、Markdown 格式
              </p>
              <button 
                style={{
                  padding: '12px 32px',
                  background: '#2563eb',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 8,
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                选择文件
              </button>
            </div>
            
            <input 
              ref={fileInputRef}
              type="file" 
              accept=".pdf,.docx,.pptx,.txt,.md"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />

            {/* 使用说明 */}
            <div style={{ marginTop: 24, background: '#0f172a', padding: 16, borderRadius: 8 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}>
                <span style={{ color: '#3b82f6', fontSize: 16 }}>📋</span>
                <div style={{ fontSize: 13, color: '#cbd5e1', fontWeight: 600 }}>使用说明</div>
              </div>
              <ul style={{ margin: '8px 0 0', paddingLeft: 20, fontSize: 12, color: '#94a3b8', lineHeight: 1.8 }}>
                <li>支持的文件格式：PDF (.pdf)、Word (.docx)、Excel (.xlsx)、PowerPoint (.pptx)、文本 (.txt)、Markdown (.md)</li>
                <li>上传后文件会自动解析并将内容分段加入知识库</li>
                <li>在对话中可以询问关于上传文件的问题</li>
                <li>单个文件大小限制：最大 20MB</li>
              </ul>
            </div>
          </>
        )}

        {/* 上传状态：上传中 */}
        {uploadStatus.state === 'uploading' && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <div style={{ 
              width: 80, 
              height: 80, 
              margin: '0 auto 24px',
              border: '4px solid #334155',
              borderTopColor: '#2563eb',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite'
            }} />
            <h3 style={{ margin: '0 0 12px', fontSize: 16, color: '#f1f5f9' }}>正在处理文件...</h3>
            <p style={{ margin: 0, fontSize: 14, color: '#94a3b8' }}>{uploadStatus.fileName}</p>
            <style>{`
              @keyframes spin {
                to { transform: rotate(360deg); }
              }
            `}</style>
          </div>
        )}

        {/* 上传状态：成功 */}
        {uploadStatus.state === 'success' && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <div style={{
              width: 80,
              height: 80,
              margin: '0 auto 24px',
              background: '#10b981',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 40
            }}>
              ✓
            </div>
            <h3 style={{ margin: '0 0 12px', fontSize: 18, color: '#10b981', fontWeight: 600 }}>上传成功！</h3>
            <div style={{ 
              background: '#0f172a', 
              padding: 16, 
              borderRadius: 8,
              marginTop: 24,
              textAlign: 'left'
            }}>
              <div style={{ marginBottom: 12, fontSize: 13, color: '#cbd5e1' }}>
                <span style={{ color: '#94a3b8' }}>成功加入</span> {uploadStatus.chunksCount} 条知识
              </div>
              <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 8 }}>
                <span style={{ fontWeight: 600 }}>文档路径：</span>{uploadStatus.fileName}
              </div>
              <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 8 }}>
                <span style={{ fontWeight: 600 }}>文件大小：</span>{((uploadStatus.fileSize || 0) / 1024 / 1024).toFixed(2)} MB
              </div>
              <div style={{ fontSize: 12, color: '#94a3b8' }}>
                <span style={{ fontWeight: 600 }}>文本分块：</span>{uploadStatus.chunksCount} 块
              </div>
            </div>
          </div>
        )}

        {/* 上传状态：失败 */}
        {uploadStatus.state === 'error' && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <div style={{
              width: 80,
              height: 80,
              margin: '0 auto 24px',
              background: '#ef4444',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 40,
              color: '#fff'
            }}>
              ×
            </div>
            <h3 style={{ margin: '0 0 12px', fontSize: 18, color: '#ef4444', fontWeight: 600 }}>上传失败</h3>
            <p style={{ margin: '0 0 24px', fontSize: 14, color: '#94a3b8' }}>{uploadStatus.message}</p>
            <button 
              onClick={handleRetry}
              style={{
                padding: '10px 24px',
                background: '#2563eb',
                color: '#fff',
                border: 'none',
                borderRadius: 8,
                fontSize: 14,
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              重新上传
            </button>
          </div>
        )}

        {/* 底部按钮 - 仅在空闲和错误状态显示关闭按钮 */}
        {(uploadStatus.state === 'idle' || uploadStatus.state === 'error') && (
          <div style={{ marginTop: 24, textAlign: 'right' }}>
            <button 
              onClick={handleClose}
              style={{
                padding: '10px 24px',
                background: '#334155',
                color: '#e2e8f0',
                border: 'none',
                borderRadius: 8,
                fontSize: 14,
                cursor: 'pointer'
              }}
            >
              取消
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default UploadModal;
