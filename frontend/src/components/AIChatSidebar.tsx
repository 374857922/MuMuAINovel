import React, { useState, useEffect, useRef } from 'react';
import { Input, Button, List, Avatar, Space, Typography, Tooltip, message, Divider, Spin } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, CopyOutlined, EnterOutlined, SwapOutlined, ClearOutlined, ThunderboltOutlined, BulbOutlined } from '@ant-design/icons';
import { aiChatApi } from '../services/api';
import ReactMarkdown from 'react-markdown';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

interface AIChatSidebarProps {
  projectId: string;
  chapterId?: string;
  selectedText?: string;
  contextText?: string;
  onInsertText: (text: string) => void;
  onReplaceText: (text: string) => void;
  visible: boolean;
  onClose?: () => void;
}

export const AIChatSidebar: React.FC<AIChatSidebarProps> = ({
  projectId,
  chapterId,
  selectedText,
  contextText,
  onInsertText,
  onReplaceText,
  visible,
  onClose
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: '你好！我是你的 AI 写作助手。选中编辑器中的文本，我可以帮你润色、扩写或检查。或者直接告诉我你的创作需求。',
      timestamp: Date.now()
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = async (prompt: string = inputValue) => {
    if (!prompt.trim() && !selectedText) return;

    const finalPrompt = prompt.trim() || "请根据选中文本提供建议"; // 如果只选中没输入，给个默认提示

    const userMsg: ChatMessage = { role: 'user', content: finalPrompt, timestamp: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    let aiContent = '';
    
    // 添加一个空的 AI 消息用于流式更新
    setMessages(prev => [...prev, { role: 'assistant', content: '', timestamp: Date.now() }]);

    try {
      await aiChatApi.chatStream({
        project_id: projectId,
        chapter_id: chapterId,
        prompt: finalPrompt,
        selected_text: selectedText,
        context_text: contextText,
        use_mcp: true
      }, {
        onChunk: (chunk) => {
          try {
            // 处理可能的 JSON 数据块
            if (chunk.startsWith('{') && chunk.endsWith('}')) {
               const data = JSON.parse(chunk);
               if (data.content) {
                 aiContent += data.content;
               }
            } else {
               aiContent += chunk;
            }
            
            setMessages(prev => {
              const newMsgs = [...prev];
              // 更新最后一条消息
              const lastIndex = newMsgs.length - 1;
              if (lastIndex >= 0 && newMsgs[lastIndex].role === 'assistant') {
                 newMsgs[lastIndex] = { ...newMsgs[lastIndex], content: aiContent };
              }
              return newMsgs;
            });
          } catch (e) {
            // 如果解析失败，直接追加（可能是纯文本）
            aiContent += chunk;
             setMessages(prev => {
              const newMsgs = [...prev];
              const lastIndex = newMsgs.length - 1;
              if (lastIndex >= 0 && newMsgs[lastIndex].role === 'assistant') {
                 newMsgs[lastIndex] = { ...newMsgs[lastIndex], content: aiContent };
              }
              return newMsgs;
            });
          }
        },
        onError: (err) => {
          console.error("AI Chat Error", err);
          message.error('AI 响应出错');
        }
      });
    } catch (error) {
      console.error('Chat error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = () => {
    setMessages([{
      role: 'assistant',
      content: '对话已清空。有什么可以帮你的吗？',
      timestamp: Date.now()
    }]);
  };

  const QuickActions = () => (
    <Space wrap style={{ marginBottom: 12 }}>
      <Button size="small" icon={<ThunderboltOutlined />} onClick={() => handleSend("润色这段文字，使其更有文采")}>润色</Button>
      <Button size="small" icon={<SwapOutlined />} onClick={() => handleSend("扩写这段内容，增加细节描写")}>扩写</Button>
      <Button size="small" icon={<BulbOutlined />} onClick={() => handleSend("根据上下文，提供3个后续情节发展的建议")}>续写建议</Button>
    </Space>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: '#fff' }}>
      {/* 顶部标题栏 */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <RobotOutlined style={{ color: '#1890ff', fontSize: 18 }} />
          <Text strong>AI 写作助手</Text>
        </Space>
        <Button type="text" icon={<ClearOutlined />} onClick={handleClear} size="small">清空</Button>
      </div>

      {/* 聊天内容区域 */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px', backgroundColor: '#fafafa' }}>
        <List
          itemLayout="horizontal"
          dataSource={messages}
          renderItem={(msg) => (
            <List.Item style={{ border: 'none', padding: '8px 0', display: 'block' }}>
              <div style={{ 
                display: 'flex', 
                flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                alignItems: 'flex-start',
                gap: 8
              }}>
                <Avatar 
                  icon={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />} 
                  style={{ backgroundColor: msg.role === 'user' ? '#87d068' : '#1890ff' }}
                />
                <div style={{ maxWidth: '85%' }}>
                  <div style={{ 
                    backgroundColor: msg.role === 'user' ? '#95de64' : '#fff', 
                    padding: '8px 12px', 
                    borderRadius: 8,
                    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                    border: msg.role === 'user' ? 'none' : '1px solid #f0f0f0'
                  }}>
                    {msg.role === 'assistant' ? (
                      <div className="markdown-body" style={{ fontSize: 14 }}>
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>
                    ) : (
                      <Text>{msg.content}</Text>
                    )}
                  </div>
                  
                  {/* AI消息的操作按钮 */}
                  {msg.role === 'assistant' && msg.content && (
                    <Space size="small" style={{ marginTop: 4, display: 'flex', opacity: 0.8 }}>
                      <Tooltip title="复制内容">
                        <Button 
                          type="text" 
                          size="small" 
                          icon={<CopyOutlined />} 
                          onClick={() => {
                            navigator.clipboard.writeText(msg.content);
                            message.success('已复制');
                          }} 
                        />
                      </Tooltip>
                      <Tooltip title="插入到光标处">
                        <Button 
                          type="text" 
                          size="small" 
                          icon={<EnterOutlined />} 
                          onClick={() => onInsertText(msg.content)} 
                        >
                          插入
                        </Button>
                      </Tooltip>
                      {selectedText && (
                        <Tooltip title="替换选中的文本">
                          <Button 
                            type="text" 
                            size="small" 
                            icon={<SwapOutlined />} 
                            onClick={() => onReplaceText(msg.content)} 
                          >
                            替换
                          </Button>
                        </Tooltip>
                      )}
                    </Space>
                  )}
                </div>
              </div>
            </List.Item>
          )}
        />
        <div ref={messagesEndRef} />
      </div>

      {/* 底部输入区域 */}
      <div style={{ padding: '12px', borderTop: '1px solid #f0f0f0' }}>
        {selectedText && (
          <div style={{ marginBottom: 8, padding: '4px 8px', background: '#e6f7ff', borderRadius: 4, fontSize: 12, border: '1px solid #91d5ff' }}>
            <Text type="secondary">已选中: </Text>
            <Text style={{ maxWidth: 200 }} ellipsis>{selectedText}</Text>
          </div>
        )}
        
        {selectedText && <QuickActions />}
        
        <div style={{ display: 'flex', gap: 8 }}>
          <TextArea
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            placeholder={selectedText ? "针对选中文本提问..." : "输入你的指令或问题..."}
            autoSize={{ minRows: 1, maxRows: 4 }}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={isLoading}
          />
          <Button 
            type="primary" 
            icon={<SendOutlined />} 
            onClick={() => handleSend()} 
            loading={isLoading}
            style={{ height: 'auto' }}
          />
        </div>
      </div>
    </div>
  );
};
