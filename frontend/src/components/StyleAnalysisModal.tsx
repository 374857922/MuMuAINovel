import React, { useState, useEffect, useCallback } from 'react';
import {
  Modal,
  Progress,
  Tag,
  List,
  Button,
  Space,
  Tooltip,
  Collapse,
  Typography,
  Divider,
  message,
  Spin,
  Empty,
  Drawer,
} from 'antd';
import {
  CheckCircleOutlined,
  WarningOutlined,
  ExclamationCircleOutlined,
  SwapOutlined,
  EditOutlined,
} from '@ant-design/icons';
import { styleApi, type ToneAnalyzeResponse, type ToneIssue } from '../services/api';
import RewriteComparePanel from './RewriteComparePanel';

const { Text, Paragraph } = Typography;
const { Panel } = Collapse;

interface StyleAnalysisModalProps {
  visible: boolean;
  onClose: () => void;
  chapterId: string;
  projectId: string;
  onContentUpdate?: (newContent: string) => void;
}

// 严重程度配置
const severityConfig: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  high: { color: 'red', icon: <ExclamationCircleOutlined />, label: '高危' },
  medium: { color: 'orange', icon: <WarningOutlined />, label: '中危' },
  low: { color: 'blue', icon: <CheckCircleOutlined />, label: '提示' },
};

// 问题类型配置
const issueTypeConfig: Record<string, string> = {
  vocabulary: '词汇问题',
  sentence_uniformity: '句式单一',
  connector_overuse: '连接词过多',
};

// 分类配置
const categoryConfig: Record<string, { label: string; color: string }> = {
  critical: { label: '高危词汇', color: 'red' },
  warning: { label: '中危词汇', color: 'orange' },
  emotional: { label: '情感套话', color: 'purple' },
  scene: { label: '场景套话', color: 'cyan' },
  transition: { label: '转折套话', color: 'gold' },
};

const StyleAnalysisModal: React.FC<StyleAnalysisModalProps> = ({
  visible,
  onClose,
  chapterId,
  projectId,
  onContentUpdate,
}) => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ToneAnalyzeResponse | null>(null);
  const [replacing, setReplacing] = useState<string | null>(null);
  const [rewriteDrawerOpen, setRewriteDrawerOpen] = useState(false);
  const [selectedIssue, setSelectedIssue] = useState<ToneIssue | null>(null);
  const [selectedText, setSelectedText] = useState<string>('');

  const analyzeChapter = useCallback(async () => {
    setLoading(true);
    try {
      const response = await styleApi.analyzeTone({ chapter_id: chapterId });
      setResult(response);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '检测失败');
    } finally {
      setLoading(false);
    }
  }, [chapterId]);

  useEffect(() => {
    if (visible && chapterId) {
      analyzeChapter();
    }
  }, [visible, chapterId, analyzeChapter]);

  const handleReplace = async (issue: ToneIssue, replacement: string) => {
    if (!issue.word || replacing) return;

    setReplacing(issue.word);
    try {
      const response = await styleApi.replaceWords({
        chapter_id: chapterId,
        replacements: [{ original: issue.word, replacement }],
      });

      if (response.success) {
        message.success(`已将「${issue.word}」替换为「${replacement}」（${response.replaced_count}处）`);
        // 通知父组件内容已更新
        if (onContentUpdate) {
          onContentUpdate(response.new_content);
        }
        // 重新检测
        analyzeChapter();
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || '替换失败');
    } finally {
      setReplacing(null);
    }
  };

  const handleReplaceAll = async () => {
    if (!result || replacing) return;

    // 收集所有可替换的问题
    const replacements: Array<{ original: string; replacement: string }> = [];

    result.issues.forEach((issue) => {
      if (issue.type === 'vocabulary' && issue.word && issue.alternatives && issue.alternatives.length > 0) {
        replacements.push({
          original: issue.word,
          replacement: issue.alternatives[0], // 使用第一个建议
        });
      }
    });

    if (replacements.length === 0) {
      message.info('没有可自动替换的问题');
      return;
    }

    setReplacing('all');
    try {
      const response = await styleApi.replaceWords({
        chapter_id: chapterId,
        replacements,
      });

      if (response.success) {
        message.success(`已替换 ${response.replaced_count} 处问题词汇`);
        if (onContentUpdate) {
          onContentUpdate(response.new_content);
        }
        analyzeChapter();
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || '批量替换失败');
    } finally {
      setReplacing(null);
    }
  };

  // 打开AI改写面板
  const handleOpenRewrite = (issue: ToneIssue) => {
    // 从positions获取上下文作为待改写文本
    let text = '';
    if (issue.positions && issue.positions.length > 0) {
      text = issue.positions[0].context || '';
    } else if (issue.word) {
      text = issue.word;
    }

    setSelectedIssue(issue);
    setSelectedText(text);
    setRewriteDrawerOpen(true);
  };

  // 处理改写结果采纳
  const handleRewriteAccept = async (rewrittenText: string, recordId?: string) => {
    if (!selectedText || !rewrittenText) return;

    try {
      // 如果有recordId，使用API应用改写
      if (recordId && chapterId) {
        const response = await styleApi.applyRewrite(recordId);
        message.success('改写已应用');
        if (onContentUpdate) {
          // 获取更新后的章节内容
          onContentUpdate(response.new_content_preview);
        }
      } else {
        // 否则直接使用替换API
        const response = await styleApi.replaceWords({
          chapter_id: chapterId,
          replacements: [{ original: selectedText, replacement: rewrittenText }],
        });
        if (response.success) {
          message.success('改写已应用');
          if (onContentUpdate) {
            onContentUpdate(response.new_content);
          }
        }
      }

      setRewriteDrawerOpen(false);
      setSelectedIssue(null);
      setSelectedText('');
      // 重新检测
      analyzeChapter();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '应用改写失败');
    }
  };

  // 处理改写拒绝
  const handleRewriteReject = () => {
    setRewriteDrawerOpen(false);
    setSelectedIssue(null);
    setSelectedText('');
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#52c41a';
    if (score >= 60) return '#faad14';
    if (score >= 40) return '#fa8c16';
    return '#f5222d';
  };

  const renderIssueItem = (issue: ToneIssue, index: number) => {
    const severity = severityConfig[issue.severity] || severityConfig.low;
    const category = issue.category ? categoryConfig[issue.category] : null;

    return (
      <List.Item key={index} style={{ padding: '12px 0' }}>
        <div style={{ width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
            <Tag color={severity.color} icon={severity.icon}>
              {severity.label}
            </Tag>
            {category && <Tag color={category.color}>{category.label}</Tag>}
            <Text strong style={{ marginLeft: 8 }}>
              {issue.word ? `「${issue.word}」` : issueTypeConfig[issue.type] || issue.type}
            </Text>
            {issue.count && issue.count > 1 && (
              <Tag style={{ marginLeft: 8 }}>出现 {issue.count} 次</Tag>
            )}
          </div>

          {issue.description && (
            <Paragraph type="secondary" style={{ marginBottom: 8, fontSize: 13 }}>
              {issue.description}
            </Paragraph>
          )}

          {issue.message && (
            <Paragraph type="secondary" style={{ marginBottom: 8, fontSize: 13 }}>
              {issue.message}
            </Paragraph>
          )}

          {issue.suggestion && (
            <Paragraph style={{ marginBottom: 8, fontSize: 13, color: '#1890ff' }}>
              💡 {issue.suggestion}
            </Paragraph>
          )}

          {issue.alternatives && issue.alternatives.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                建议替换为：
              </Text>
              <Space wrap style={{ marginTop: 4 }}>
                {issue.alternatives.map((alt, i) => (
                  <Button
                    key={i}
                    size="small"
                    icon={<SwapOutlined />}
                    onClick={() => handleReplace(issue, alt)}
                    loading={replacing === issue.word}
                    disabled={replacing !== null}
                  >
                    {alt}
                  </Button>
                ))}
                <Tooltip title="使用AI智能改写整句">
                  <Button
                    size="small"
                    type="primary"
                    ghost
                    icon={<EditOutlined />}
                    onClick={() => handleOpenRewrite(issue)}
                    disabled={replacing !== null}
                  >
                    AI改写
                  </Button>
                </Tooltip>
              </Space>
            </div>
          )}

          {issue.positions && issue.positions.length > 0 && (
            <Collapse ghost size="small" style={{ marginTop: 8 }}>
              <Panel header={`查看上下文（${issue.positions.length}处）`} key="1">
                {issue.positions.slice(0, 3).map((pos, i) => (
                  <div
                    key={i}
                    style={{
                      padding: '8px',
                      background: '#f5f5f5',
                      borderRadius: 4,
                      marginBottom: 4,
                      fontSize: 13,
                    }}
                  >
                    <Text type="secondary">...{pos.context}...</Text>
                  </div>
                ))}
                {issue.positions.length > 3 && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    还有 {issue.positions.length - 3} 处...
                  </Text>
                )}
              </Panel>
            </Collapse>
          )}
        </div>
      </List.Item>
    );
  };

  const groupedIssues = result?.issues.reduce(
    (acc, issue) => {
      acc[issue.severity] = acc[issue.severity] || [];
      acc[issue.severity].push(issue);
      return acc;
    },
    {} as Record<string, ToneIssue[]>
  );

  return (
    <>
    <Modal
      title="文风检测"
      open={visible}
      onCancel={onClose}
      width={700}
      footer={
        result && result.issue_count > 0
          ? [
              <Button key="close" onClick={onClose}>
                关闭
              </Button>,
              <Button
                key="refresh"
                onClick={analyzeChapter}
                loading={loading}
                disabled={replacing !== null}
              >
                重新检测
              </Button>,
              <Button
                key="replace-all"
                type="primary"
                onClick={handleReplaceAll}
                loading={replacing === 'all'}
                disabled={replacing !== null && replacing !== 'all'}
              >
                一键替换高危词汇
              </Button>,
            ]
          : [
              <Button key="close" onClick={onClose}>
                关闭
              </Button>,
              <Button key="refresh" onClick={analyzeChapter} loading={loading}>
                重新检测
              </Button>,
            ]
      }
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: '#666' }}>正在分析文风...</div>
        </div>
      ) : result ? (
        <div>
          {/* 评分区域 */}
          <div style={{ textAlign: 'center', marginBottom: 24 }}>
            <Progress
              type="dashboard"
              percent={result.score}
              strokeColor={getScoreColor(result.score)}
              format={(percent) => (
                <div>
                  <div style={{ fontSize: 28, fontWeight: 600 }}>{percent}</div>
                  <div style={{ fontSize: 14, color: '#666' }}>自然度</div>
                </div>
              )}
            />
            <div style={{ marginTop: 12 }}>
              <Tag
                color={
                  result.level === '自然'
                    ? 'green'
                    : result.level === '一般'
                      ? 'blue'
                      : result.level === '明显'
                        ? 'orange'
                        : 'red'
                }
                style={{ fontSize: 14, padding: '4px 12px' }}
              >
                {result.level}
              </Tag>
            </div>
            <Paragraph style={{ marginTop: 12, color: '#666' }}>{result.summary}</Paragraph>
          </div>

          <Divider />

          {/* 统计信息 */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-around',
              marginBottom: 16,
              padding: '12px',
              background: '#fafafa',
              borderRadius: 8,
            }}
          >
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 20, fontWeight: 600 }}>{result.stats.word_count}</div>
              <div style={{ fontSize: 12, color: '#666' }}>总字数</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 20, fontWeight: 600 }}>{result.stats.sentence_count}</div>
              <div style={{ fontSize: 12, color: '#666' }}>句子数</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 20, fontWeight: 600 }}>
                {result.stats.avg_sentence_length.toFixed(1)}
              </div>
              <div style={{ fontSize: 12, color: '#666' }}>平均句长</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 20, fontWeight: 600 }}>{result.issue_count}</div>
              <div style={{ fontSize: 12, color: '#666' }}>问题数</div>
            </div>
          </div>

          {/* 问题列表 */}
          {result.issue_count > 0 ? (
            <div style={{ maxHeight: 400, overflow: 'auto' }}>
              {groupedIssues?.high && groupedIssues.high.length > 0 && (
                <>
                  <div style={{ marginBottom: 8 }}>
                    <Tag color="red" icon={<ExclamationCircleOutlined />}>
                      高危问题 ({groupedIssues.high.length})
                    </Tag>
                  </div>
                  <List
                    dataSource={groupedIssues.high}
                    renderItem={renderIssueItem}
                    split={false}
                  />
                </>
              )}

              {groupedIssues?.medium && groupedIssues.medium.length > 0 && (
                <>
                  <div style={{ marginTop: 16, marginBottom: 8 }}>
                    <Tag color="orange" icon={<WarningOutlined />}>
                      中危问题 ({groupedIssues.medium.length})
                    </Tag>
                  </div>
                  <List
                    dataSource={groupedIssues.medium}
                    renderItem={renderIssueItem}
                    split={false}
                  />
                </>
              )}

              {groupedIssues?.low && groupedIssues.low.length > 0 && (
                <>
                  <div style={{ marginTop: 16, marginBottom: 8 }}>
                    <Tag color="blue" icon={<CheckCircleOutlined />}>
                      提示 ({groupedIssues.low.length})
                    </Tag>
                  </div>
                  <List
                    dataSource={groupedIssues.low}
                    renderItem={renderIssueItem}
                    split={false}
                  />
                </>
              )}
            </div>
          ) : (
            <Empty description="文本风格自然，未发现明显的AI腔调痕迹" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </div>
      ) : (
        <Empty description="点击「重新检测」开始分析" />
      )}
    </Modal>

    {/* AI智能改写抽屉 */}
    <Drawer
      title="AI智能改写"
      placement="right"
      width={800}
      open={rewriteDrawerOpen}
      onClose={handleRewriteReject}
      destroyOnClose
    >
      {selectedText && (
        <RewriteComparePanel
          originalText={selectedText}
          chapterId={chapterId}
          projectId={projectId}
          issue={
            selectedIssue
              ? {
                  word: selectedIssue.word || undefined,
                  alternatives: selectedIssue.alternatives || undefined,
                  description: selectedIssue.description || undefined,
                }
              : undefined
          }
          onAccept={handleRewriteAccept}
          onReject={handleRewriteReject}
          onClose={handleRewriteReject}
        />
      )}
    </Drawer>
  </>
  );
};

export default StyleAnalysisModal;
