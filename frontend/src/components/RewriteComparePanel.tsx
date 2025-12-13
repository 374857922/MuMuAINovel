import React, { useState, useCallback } from 'react';
import {
  Card,
  Button,
  Space,
  Typography,
  Spin,
  message,
  Tooltip,
  Tag,
  Divider,
  Radio,
} from 'antd';
import {
  EditOutlined,
  CheckOutlined,
  CloseOutlined,
  SyncOutlined,
  CopyOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import { styleApi } from '../services/api';

const { Text, Paragraph } = Typography;

export interface RewriteComparePanelProps {
  originalText: string;
  chapterId?: string;
  projectId?: string;
  issue?: {
    word?: string;
    alternatives?: string[];
    description?: string;
  };
  context?: string;
  onAccept?: (rewrittenText: string, recordId?: string) => void;
  onReject?: () => void;
  onClose?: () => void;
}

type RewriteType = 'replace' | 'rewrite' | 'restructure';

const rewriteTypeConfig: Record<
  RewriteType,
  { label: string; description: string; color: string }
> = {
  replace: {
    label: '词汇替换',
    description: '保留句式，只替换特定词',
    color: 'blue',
  },
  rewrite: {
    label: '句子改写',
    description: '保持原意，调整表达方式',
    color: 'green',
  },
  restructure: {
    label: '段落重构',
    description: '打散重组，提升多样性',
    color: 'purple',
  },
};

const RewriteComparePanel: React.FC<RewriteComparePanelProps> = ({
  originalText,
  chapterId,
  projectId,
  issue,
  context,
  onAccept,
  onReject,
  onClose,
}) => {
  const [rewriteType, setRewriteType] = useState<RewriteType>(
    issue?.word ? 'replace' : 'rewrite'
  );
  const [rewriting, setRewriting] = useState(false);
  const [rewrittenText, setRewrittenText] = useState<string>('');
  const [recordId, setRecordId] = useState<string | undefined>();
  const [streamingText, setStreamingText] = useState<string>('');

  const handleRewrite = useCallback(async () => {
    setRewriting(true);
    setRewrittenText('');
    setStreamingText('');
    setRecordId(undefined);

    try {
      const result = await styleApi.rewriteStream(
        {
          text: originalText,
          chapter_id: chapterId,
          project_id: projectId,
          rewrite_type: rewriteType,
          issue,
          context,
        },
        {
          onChunk: (chunk) => {
            setStreamingText((prev) => prev + chunk);
          },
          onProgress: (msg, progress, status) => {
            if (status === 'success') {
              message.success('改写完成');
            }
          },
          onError: (error) => {
            message.error(error || '改写失败');
          },
        }
      );

      if (result) {
        setRewrittenText(result.rewritten);
        setRecordId(result.record_id);
      }
    } catch (error: any) {
      message.error(error.message || '改写失败');
    } finally {
      setRewriting(false);
    }
  }, [originalText, chapterId, projectId, rewriteType, issue, context]);

  const handleAccept = () => {
    const finalText = rewrittenText || streamingText;
    if (finalText && onAccept) {
      onAccept(finalText, recordId);
    }
  };

  const handleReject = async () => {
    if (recordId) {
      try {
        await styleApi.updateRewriteStatus(recordId, 'rejected');
      } catch (error) {
        // 静默失败，不影响UI
      }
    }
    if (onReject) {
      onReject();
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    message.success('已复制到剪贴板');
  };

  const displayText = rewrittenText || streamingText;

  const renderDiff = () => {
    return (
      <div style={{ display: 'flex', gap: 16 }}>
        <Card
          size="small"
          title={
            <Space>
              <Text type="secondary">原文</Text>
              <Tooltip title="复制原文">
                <Button
                  type="text"
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => copyToClipboard(originalText)}
                />
              </Tooltip>
            </Space>
          }
          style={{ flex: 1, background: '#fff7e6' }}
        >
          <Paragraph
            style={{
              marginBottom: 0,
              whiteSpace: 'pre-wrap',
              fontSize: 14,
              lineHeight: 1.8,
            }}
          >
            {originalText}
          </Paragraph>
        </Card>

        <div style={{ display: 'flex', alignItems: 'center' }}>
          <SwapOutlined style={{ fontSize: 20, color: '#1890ff' }} />
        </div>

        <Card
          size="small"
          title={
            <Space>
              <Text style={{ color: '#52c41a' }}>改写后</Text>
              {displayText && (
                <Tooltip title="复制改写结果">
                  <Button
                    type="text"
                    size="small"
                    icon={<CopyOutlined />}
                    onClick={() => copyToClipboard(displayText)}
                  />
                </Tooltip>
              )}
            </Space>
          }
          style={{ flex: 1, background: '#f6ffed' }}
        >
          {rewriting && !streamingText ? (
            <div style={{ textAlign: 'center', padding: 20 }}>
              <Spin />
              <div style={{ marginTop: 8, color: '#666' }}>正在改写...</div>
            </div>
          ) : (
            <Paragraph
              style={{
                marginBottom: 0,
                whiteSpace: 'pre-wrap',
                fontSize: 14,
                lineHeight: 1.8,
              }}
            >
              {displayText || (
                <Text type="secondary">点击下方按钮开始AI改写</Text>
              )}
              {rewriting && <span className="typing-cursor">|</span>}
            </Paragraph>
          )}
        </Card>
      </div>
    );
  };

  return (
    <div style={{ padding: 16 }}>
      <div style={{ marginBottom: 16 }}>
        <Text strong>改写模式：</Text>
        <Radio.Group
          value={rewriteType}
          onChange={(e) => setRewriteType(e.target.value)}
          style={{ marginLeft: 12 }}
          disabled={rewriting}
        >
          {Object.entries(rewriteTypeConfig).map(([key, config]) => (
            <Tooltip key={key} title={config.description}>
              <Radio.Button value={key}>
                <Tag color={config.color} style={{ margin: 0 }}>
                  {config.label}
                </Tag>
              </Radio.Button>
            </Tooltip>
          ))}
        </Radio.Group>
      </div>

      {issue && (
        <div
          style={{
            marginBottom: 16,
            padding: 12,
            background: '#fffbe6',
            borderRadius: 6,
            border: '1px solid #ffe58f',
          }}
        >
          <Text type="secondary">
            检测到问题：
            {issue.word && (
              <Tag color="orange" style={{ marginLeft: 8 }}>
                {issue.word}
              </Tag>
            )}
            {issue.description && <span> - {issue.description}</span>}
          </Text>
          {issue.alternatives && issue.alternatives.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <Text type="secondary">建议词汇：</Text>
              <Space style={{ marginLeft: 8 }}>
                {issue.alternatives.map((alt, i) => (
                  <Tag key={i} color="blue">
                    {alt}
                  </Tag>
                ))}
              </Space>
            </div>
          )}
        </div>
      )}

      {renderDiff()}

      <Divider />

      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <Button onClick={onClose}>关闭</Button>

        <Space>
          {displayText && (
            <>
              <Button
                icon={<CloseOutlined />}
                onClick={handleReject}
                disabled={rewriting}
              >
                放弃
              </Button>
              <Button
                type="primary"
                icon={<CheckOutlined />}
                onClick={handleAccept}
                disabled={rewriting}
              >
                采纳改写
              </Button>
            </>
          )}
          <Button
            type={displayText ? 'default' : 'primary'}
            icon={displayText ? <SyncOutlined /> : <EditOutlined />}
            onClick={handleRewrite}
            loading={rewriting}
          >
            {displayText ? '重新改写' : 'AI智能改写'}
          </Button>
        </Space>
      </div>

      <style>{`
        .typing-cursor {
          display: inline-block;
          animation: blink 1s step-end infinite;
          color: #1890ff;
        }
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
};

export default RewriteComparePanel;
