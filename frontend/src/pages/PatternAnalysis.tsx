import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card,
  Progress,
  Tag,
  List,
  Space,
  Collapse,
  Typography,
  Divider,
  message,
  Spin,
  Empty,
  Alert,
  Statistic,
  Row,
  Col,
  Button,
  Result,
} from 'antd';
import {
  ExclamationCircleOutlined,
  BulbOutlined,
  ClockCircleOutlined,
  SmileOutlined,
  ReloadOutlined,
  LineChartOutlined,
} from '@ant-design/icons';
import { styleApi, type PatternAnalysisResponse, type PatternItem } from '../services/api';

const { Text, Paragraph, Title } = Typography;
const { Panel } = Collapse;

// 开场类型中文映射
const openingTypeNames: Record<string, string> = {
  time: '时间开场',
  weather: '天气/环境',
  dialogue: '对话开场',
  action: '动作开场',
  other: '其他方式',
};

// 情感类型中文映射
const emotionNames: Record<string, string> = {
  happy: '开心',
  sad: '悲伤',
  angry: '愤怒',
  fear: '恐惧',
  surprise: '惊讶',
};

const PatternAnalysis: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PatternAnalysisResponse | null>(null);
  const [hasAnalyzed, setHasAnalyzed] = useState(false);

  useEffect(() => {
    if (projectId) {
      loadExistingAnalysis();
    }
  }, [projectId]);

  const loadExistingAnalysis = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const existing = await styleApi.getPatterns(projectId);
      if (existing.status === 'success') {
        setResult(existing);
        setHasAnalyzed(true);
      }
    } catch (error) {
      // 没有已有结果，不显示错误
    } finally {
      setLoading(false);
    }
  };

  const runAnalysis = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const response = await styleApi.analyzePatterns(projectId);
      setResult(response);
      setHasAnalyzed(true);
      if (response.status === 'success') {
        message.success('分析完成');
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || '分析失败');
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#52c41a';
    if (score >= 60) return '#1890ff';
    if (score >= 40) return '#faad14';
    return '#f5222d';
  };

  const getLevelColor = (level: string) => {
    switch (level) {
      case '多样丰富':
        return 'green';
      case '较为多样':
        return 'blue';
      case '套路化明显':
        return 'orange';
      case '高度套路化':
        return 'red';
      default:
        return 'default';
    }
  };

  const renderPatternItem = (pattern: PatternItem, index: number) => (
    <List.Item key={index}>
      <Card size="small" style={{ width: '100%' }}>
        <div style={{ marginBottom: 8 }}>
          <Space>
            <Tag color={pattern.count >= 5 ? 'red' : pattern.count >= 3 ? 'orange' : 'blue'}>
              出现 {pattern.count} 次
            </Tag>
            {pattern.is_opening_pattern && <Tag color="purple">开场模式</Tag>}
            {pattern.is_ending_pattern && <Tag color="cyan">结尾模式</Tag>}
          </Space>
        </div>
        <Paragraph
          style={{
            fontSize: 13,
            background: '#f5f5f5',
            padding: 8,
            borderRadius: 4,
            marginBottom: 8,
          }}
        >
          <Text code>{pattern.template}</Text>
        </Paragraph>
        <Collapse ghost size="small">
          <Panel header={`查看示例（${pattern.examples.length}个）`} key="1">
            {pattern.examples.map((example, i) => (
              <div
                key={i}
                style={{
                  padding: '6px 8px',
                  background: '#fafafa',
                  borderRadius: 4,
                  marginBottom: 4,
                  fontSize: 12,
                }}
              >
                {example.length > 80 ? example.slice(0, 80) + '...' : example}
              </div>
            ))}
          </Panel>
        </Collapse>
        <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
          出现章节：{pattern.chapters.slice(0, 5).join(', ')}
          {pattern.chapters.length > 5 && ` 等${pattern.chapters.length}章`}
        </div>
      </Card>
    </List.Item>
  );

  const renderOpeningAnalysis = () => {
    if (!result?.opening_analysis) return null;

    const { categories, examples, dominant_type, dominant_ratio, is_monotonous, suggestion } =
      result.opening_analysis;

    return (
      <Card
        title={
          <Space>
            <ClockCircleOutlined />
            <span>开场方式分析</span>
            {is_monotonous && <Tag color="orange">单一</Tag>}
          </Space>
        }
        size="small"
        style={{ marginBottom: 16 }}
      >
        <Row gutter={16} style={{ marginBottom: 16 }}>
          {Object.entries(categories).map(([type, count]) => (
            <Col span={4} key={type}>
              <Statistic
                title={openingTypeNames[type] || type}
                value={count as number}
                suffix="章"
                valueStyle={{
                  fontSize: 20,
                  color: type === dominant_type ? getScoreColor(100 - dominant_ratio * 100) : undefined,
                }}
              />
            </Col>
          ))}
        </Row>

        {is_monotonous && (
          <Alert
            message={`${Math.round(dominant_ratio * 100)}% 的章节使用「${openingTypeNames[dominant_type] || dominant_type}」`}
            description={suggestion}
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
          />
        )}

        {Object.entries(examples).length > 0 && (
          <Collapse ghost size="small">
            {Object.entries(examples).map(([type, exampleList]) => (
              <Panel
                header={`${openingTypeNames[type] || type} 示例 (${(exampleList as any[]).length})`}
                key={type}
              >
                {(exampleList as any[]).map((ex, i) => (
                  <div
                    key={i}
                    style={{
                      padding: '6px 8px',
                      background: '#fafafa',
                      borderRadius: 4,
                      marginBottom: 4,
                      fontSize: 12,
                    }}
                  >
                    <Tag size="small">第{ex.chapter}章</Tag>
                    {ex.text}
                  </div>
                ))}
              </Panel>
            ))}
          </Collapse>
        )}
      </Card>
    );
  };

  const renderEmotionDiversity = () => {
    if (!result?.emotion_diversity) return null;

    const { emotions, diversity_score, most_concentrated_emotion, suggestion } = result.emotion_diversity;

    return (
      <Card
        title={
          <Space>
            <SmileOutlined />
            <span>情感词汇多样性</span>
            <Tag color={diversity_score >= 70 ? 'green' : diversity_score >= 40 ? 'orange' : 'red'}>
              {diversity_score}分
            </Tag>
          </Space>
        }
        size="small"
        style={{ marginBottom: 16 }}
      >
        {most_concentrated_emotion && (
          <Alert
            message={`「${emotionNames[most_concentrated_emotion] || most_concentrated_emotion}」表达较为集中`}
            description={suggestion}
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
          />
        )}

        <Collapse ghost size="small">
          {Object.entries(emotions).map(([emotion, data]: [string, any]) => (
            <Panel
              header={
                <Space>
                  <span>{emotionNames[emotion] || emotion}</span>
                  <Tag>{data.total_count}次</Tag>
                  <Tag color={data.concentration > 0.7 ? 'red' : 'default'}>
                    集中度 {Math.round(data.concentration * 100)}%
                  </Tag>
                </Space>
              }
              key={emotion}
            >
              <List
                size="small"
                dataSource={data.expressions.slice(0, 5)}
                renderItem={(item: [string, number]) => (
                  <List.Item>
                    <Space>
                      <Text>「{item[0]}」</Text>
                      <Tag>{item[1]}次</Tag>
                    </Space>
                  </List.Item>
                )}
              />
            </Panel>
          ))}
        </Collapse>
      </Card>
    );
  };

  const renderSuggestions = () => {
    if (!result?.suggestions || result.suggestions.length === 0) return null;

    return (
      <Card
        title={
          <Space>
            <BulbOutlined />
            <span>改进建议</span>
          </Space>
        }
        size="small"
      >
        <List
          size="small"
          dataSource={result.suggestions}
          renderItem={(item, index) => (
            <List.Item>
              <Space>
                <Tag color="blue">{index + 1}</Tag>
                <Text>{item}</Text>
              </Space>
            </List.Item>
          )}
        />
      </Card>
    );
  };

  if (loading && !hasAnalyzed) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
        <div style={{ marginTop: 16, color: '#666' }}>加载中...</div>
      </div>
    );
  }

  // 未分析状态
  if (!hasAnalyzed && !result) {
    return (
      <div style={{ height: '100%', overflow: 'auto' }}>
        <Result
          icon={<LineChartOutlined style={{ color: '#1890ff' }} />}
          title="套路化分析"
          subTitle="分析项目所有章节，检测重复句式模式、开场方式单一性、情感表达词汇多样性"
          extra={
            <Button type="primary" size="large" onClick={runAnalysis} loading={loading}>
              开始分析
            </Button>
          }
        >
          <div style={{ textAlign: 'left', maxWidth: 600, margin: '0 auto' }}>
            <Alert
              message="分析说明"
              description={
                <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
                  <li>需要至少 5 个已写章节才能进行分析</li>
                  <li>分析会检测跨章节的句式重复模式</li>
                  <li>分析开场方式是否过于单一（如总是用时间开场）</li>
                  <li>检测情感表达词汇是否过于集中</li>
                </ul>
              }
              type="info"
              showIcon
            />
          </div>
        </Result>
      </div>
    );
  }

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: '0 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          套路化分析
        </Title>
        <Button icon={<ReloadOutlined />} onClick={runAnalysis} loading={loading}>
          重新分析
        </Button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: '#666' }}>
            正在分析项目套路化程度...
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>
              分析所有章节的句式模式、开场方式、情感表达
            </Text>
          </div>
        </div>
      ) : result?.status === 'success' ? (
        <div>
          {/* 总体评分 */}
          <Card style={{ marginBottom: 16 }}>
            <Row gutter={24} align="middle">
              <Col span={8} style={{ textAlign: 'center' }}>
                <Progress
                  type="dashboard"
                  percent={result.score}
                  strokeColor={getScoreColor(result.score || 0)}
                  format={(percent) => (
                    <div>
                      <div style={{ fontSize: 32, fontWeight: 600 }}>{percent}</div>
                      <div style={{ fontSize: 14, color: '#666' }}>多样性评分</div>
                    </div>
                  )}
                  size={180}
                />
              </Col>
              <Col span={16}>
                <Row gutter={16}>
                  <Col span={8}>
                    <Statistic
                      title="评级"
                      value={result.level}
                      valueStyle={{ color: getLevelColor(result.level || '') === 'green' ? '#52c41a' : getLevelColor(result.level || '') === 'red' ? '#f5222d' : '#faad14' }}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic title="分析章节" value={result.chapters_analyzed} suffix="章" />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="重复模式"
                      value={result.patterns_found}
                      suffix="个"
                      valueStyle={{ color: (result.patterns_found || 0) > 10 ? '#f5222d' : undefined }}
                    />
                  </Col>
                </Row>
                <div style={{ marginTop: 16 }}>
                  <Text type="secondary">
                    {result.score && result.score >= 80
                      ? '您的写作风格多样丰富，句式变化自然，情感表达多样。'
                      : result.score && result.score >= 60
                        ? '写作风格较为多样，但仍有一些重复模式值得关注。'
                        : result.score && result.score >= 40
                          ? '检测到明显的套路化倾向，建议参考下方建议改进。'
                          : '套路化程度较高，建议重点关注重复模式和表达多样性。'}
                  </Text>
                </div>
              </Col>
            </Row>
          </Card>

          <Row gutter={16}>
            <Col span={12}>
              {/* 开场方式分析 */}
              {renderOpeningAnalysis()}
            </Col>
            <Col span={12}>
              {/* 情感词汇多样性 */}
              {renderEmotionDiversity()}
            </Col>
          </Row>

          {/* 重复模式列表 */}
          {result.top_patterns && result.top_patterns.length > 0 && (
            <Card
              title={
                <Space>
                  <ExclamationCircleOutlined />
                  <span>重复句式模式</span>
                  <Tag color="red">{result.top_patterns.length}个</Tag>
                </Space>
              }
              size="small"
              style={{ marginBottom: 16 }}
            >
              <div style={{ maxHeight: 400, overflow: 'auto' }}>
                <List dataSource={result.top_patterns} renderItem={renderPatternItem} split={false} />
              </div>
            </Card>
          )}

          {/* 改进建议 */}
          {renderSuggestions()}
        </div>
      ) : result?.status === 'insufficient_data' ? (
        <Result
          status="warning"
          title="章节数量不足"
          subTitle={result.message}
          extra={
            <div>
              <Text type="secondary">当前章节数：{result.current_chapters}</Text>
              <br />
              <Text type="secondary">至少需要 5 个章节才能进行套路化分析</Text>
            </div>
          }
        />
      ) : result?.status === 'no_content' ? (
        <Result status="info" title="章节内容为空" subTitle={result.message} />
      ) : (
        <Result
          status="info"
          title={result?.message || '尚未进行分析'}
          extra={
            <Button type="primary" onClick={runAnalysis} loading={loading}>
              开始分析
            </Button>
          }
        />
      )}
    </div>
  );
};

export default PatternAnalysis;
