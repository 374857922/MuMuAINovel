import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Button,
  Card,
  Col,
  message,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Tag,
  Typography,
  Switch,
  Tooltip
} from 'antd';
import {
  NodeExpandOutlined,
  RadarChartOutlined,
  ReloadOutlined,
  DownOutlined,
  RightOutlined,
  SettingOutlined
} from '@ant-design/icons';
import { chapterGraphApi } from '../services/api';
import { GraphVisualization } from '../components_new/GraphVisualization';

const { Title, Text } = Typography;
const { Option } = Select;

interface ChapterGraphData {
  nodes: Array<{
    id: string;
    title: string;
    chapterNumber: number;
    importance: number;
    size: number;
  }>;
  links: Array<{
    source: string;
    target: string;
    type: string;
    description: string;
    strength: number;
    importance: number;
  }>;
  summary: {
    totalNodes: number;
    totalLinks: number;
    linkTypes: string[];
  };
}

interface ChapterStats {
  summary: {
    totalLinks: number;
    totalChapters: number;
    density: number;
    coverage: number;
  };
  byType: Record<string, number>;
  byImportance: {
    high: number;
    medium: number;
    low: number;
  };
}

export const ChapterGraph: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const [loading, setLoading] = useState(false);
  const [graphData, setGraphData] = useState<ChapterGraphData | null>(null);
  const [stats, setStats] = useState<ChapterStats | null>(null);
  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [selectedLinkType, setSelectedLinkType] = useState<string>('all');
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);

  useEffect(() => {
    if (projectId) {
      loadGraphData();
      loadStats();
    }
  }, [projectId]);

  const handleAnalyzeRelationships = async () => {
    if (!projectId) return;

    setAnalyzeLoading(true);
    try {
      const response = await chapterGraphApi.analyzeRelationships(projectId);
      message.success(`成功分析 ${response.count} 个章节关系`);
      await loadGraphData();
      await loadStats();
    } catch (error) {
      message.error('分析章节关系失败');
    } finally {
      setAnalyzeLoading(false);
    }
  };

  const loadGraphData = async () => {
    if (!projectId) return;

    setLoading(true);
    try {
      const response = await chapterGraphApi.getGraphData(projectId);
      setGraphData(response);
    } catch (error) {
      message.error('加载图谱数据失败');
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    if (!projectId) return;

    try {
      const response = await chapterGraphApi.getStats(projectId);
      setStats(response);
    } catch (error) {
      console.error('加载统计信息失败:', error);
    }
  };

  const handleFilterByType = (type: string) => {
    setSelectedLinkType(type);
  };

  const handleNodeClick = (node: any) => {
    setSelectedNode(node);
    if (!showSidebar) setShowSidebar(true);
  };

  // 初始加载中
  if (!graphData && loading) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', paddingTop: 100 }}>
        <Spin size="large" tip="加载图谱数据..." />
      </div>
    );
  }

  const summaryStats = stats?.summary || { totalChapters: 0, totalLinks: 0, density: 0, coverage: 0 };
  const linkTypes = graphData?.summary?.linkTypes || [];

  return (
    <div style={{ 
      padding: '16px', 
      background: '#f0f2f5', 
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    }}>
      {/* 可折叠控制面板 */}
      <Card 
        size="small"
        style={{ marginBottom: 12, flexShrink: 0 }}
        bodyStyle={{ padding: panelCollapsed ? 0 : '12px 16px' }}
      >
        {/* 标题栏 */}
        <div 
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            cursor: 'pointer',
            padding: panelCollapsed ? '8px 16px' : 0,
            marginBottom: panelCollapsed ? 0 : 12
          }}
          onClick={() => setPanelCollapsed(!panelCollapsed)}
        >
          <Space>
            {panelCollapsed ? <RightOutlined /> : <DownOutlined />}
            <Title level={5} style={{ margin: 0 }}>
              <RadarChartOutlined /> 章节关系图谱
            </Title>
            {panelCollapsed && (
              <Space size="large" style={{ marginLeft: 24 }}>
                <Text type="secondary">章节: {summaryStats.totalChapters}</Text>
                <Text type="secondary">关系: {summaryStats.totalLinks}</Text>
                {summaryStats.coverage > 0 && (
                  <Tag color={summaryStats.coverage > 0.7 ? 'green' : 'orange'}>
                    覆盖率 {(summaryStats.coverage * 100).toFixed(0)}%
                  </Tag>
                )}
              </Space>
            )}
          </Space>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {panelCollapsed ? '展开' : '收起'}
          </Text>
        </div>

        {/* 展开内容 */}
        {!panelCollapsed && (
          <>
            {/* 统计信息 */}
            <Row gutter={12} style={{ marginBottom: 12 }}>
              <Col xs={12} sm={6}>
                <Card size="small" bodyStyle={{ padding: '8px 12px' }}>
                  <Statistic title="章节数" value={summaryStats.totalChapters} valueStyle={{ fontSize: 20 }} />
                </Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card size="small" bodyStyle={{ padding: '8px 12px' }}>
                  <Statistic title="关系数" value={summaryStats.totalLinks} valueStyle={{ fontSize: 20 }} />
                </Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card size="small" bodyStyle={{ padding: '8px 12px' }}>
                  <Statistic 
                    title="密度" 
                    value={summaryStats.density} 
                    precision={2}
                    valueStyle={{ fontSize: 20 }} 
                  />
                </Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card size="small" bodyStyle={{ padding: '8px 12px' }}>
                  <Statistic 
                    title="覆盖率" 
                    value={summaryStats.coverage * 100} 
                    precision={0}
                    suffix="%"
                    valueStyle={{ 
                      fontSize: 20,
                      color: summaryStats.coverage > 0.7 ? '#52c41a' : '#faad14' 
                    }} 
                  />
                </Card>
              </Col>
            </Row>

            {/* 操作栏 */}
            <Row gutter={16} align="middle">
              <Col>
                <Space>
                  <Button
                    type="primary"
                    icon={<ReloadOutlined />}
                    loading={analyzeLoading}
                    onClick={handleAnalyzeRelationships}
                  >
                    分析关系
                  </Button>
                  <Button onClick={() => loadGraphData()} icon={<ReloadOutlined />}>
                    刷新
                  </Button>
                </Space>
              </Col>
              <Col>
                <Space>
                  <Text type="secondary">关系类型:</Text>
                  <Select
                    value={selectedLinkType}
                    onChange={handleFilterByType}
                    style={{ width: 120 }}
                    size="small"
                  >
                    <Option value="all">全部</Option>
                    {linkTypes.map(type => (
                      <Option key={type} value={type}>{type}</Option>
                    ))}
                  </Select>
                </Space>
              </Col>
              <Col flex="auto" style={{ textAlign: 'right' }}>
                <Space>
                  <Tooltip title="显示/隐藏侧边栏">
                    <Switch 
                      checked={showSidebar} 
                      onChange={setShowSidebar}
                      checkedChildren="侧栏"
                      unCheckedChildren="隐藏"
                      size="small"
                    />
                  </Tooltip>
                </Space>
              </Col>
            </Row>
          </>
        )}
      </Card>

      {/* 图谱主体 */}
      <Card
        size="small"
        style={{ 
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          minHeight: 0
        }}
        bodyStyle={{ 
          flex: 1,
          display: 'flex',
          overflow: 'hidden',
          padding: 12
        }}
      >
        <Row gutter={12} style={{ flex: 1, minHeight: 0 }}>
          {/* 图谱区域 */}
          <Col span={showSidebar ? 18 : 24} style={{ height: '100%' }}>
            {graphData ? (
              <GraphVisualization
                graphData={graphData}
                loading={loading}
                selectedLinkType={selectedLinkType}
                onNodeClick={handleNodeClick}
              />
            ) : (
              <div style={{ 
                height: '100%', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                background: '#fafafa',
                borderRadius: 6
              }}>
                <Space direction="vertical" align="center">
                  <NodeExpandOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
                  <Text type="secondary">暂无图谱数据</Text>
                  <Button type="primary" onClick={handleAnalyzeRelationships} loading={analyzeLoading}>
                    开始分析
                  </Button>
                </Space>
              </div>
            )}
          </Col>

          {/* 侧边栏 */}
          {showSidebar && (
            <Col span={6} style={{ height: '100%', overflow: 'auto' }}>
              {/* 选中章节详情 */}
              <Card 
                title={<Text strong style={{ fontSize: 13 }}>章节详情</Text>} 
                size="small"
                style={{ marginBottom: 12 }}
                bodyStyle={{ padding: '8px 12px' }}
              >
                {selectedNode ? (
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Text strong>第 {selectedNode.chapterNumber} 章</Text>
                    <Text ellipsis style={{ fontSize: 12 }}>{selectedNode.title}</Text>
                    <div style={{ marginTop: 4 }}>
                      <Tag color="blue">重要性: {selectedNode.importance}</Tag>
                    </div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      关联: {graphData?.links.filter(
                        l => l.source === selectedNode.id || l.target === selectedNode.id
                      ).length || 0} 个章节
                    </Text>
                  </Space>
                ) : (
                  <Text type="secondary" style={{ fontSize: 12 }}>点击节点查看详情</Text>
                )}
              </Card>

              {/* 关系类型统计 */}
              <Card 
                title={<Text strong style={{ fontSize: 13 }}>关系统计</Text>} 
                size="small"
                bodyStyle={{ padding: '8px 12px' }}
              >
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  {stats?.byType && Object.entries(stats.byType).map(([type, count]) => (
                    <div key={type} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Tag style={{ margin: 0, fontSize: 11 }}>{type}</Tag>
                      <Text strong style={{ fontSize: 12 }}>{count}</Text>
                    </div>
                  ))}
                  {(!stats?.byType || Object.keys(stats.byType).length === 0) && (
                    <Text type="secondary" style={{ fontSize: 12 }}>暂无数据</Text>
                  )}
                </Space>
              </Card>
            </Col>
          )}
        </Row>
      </Card>
    </div>
  );
};
