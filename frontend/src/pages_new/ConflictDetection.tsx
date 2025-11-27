import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Button,
  Tag,
  Modal,
  Spin,
  Alert,
  Typography,
  Space,
  message,
  Row,
  Col,
  Card,
  Statistic,
  Switch,
  Tooltip,
  Radio,
  Popconfirm
} from 'antd';
import {
  BugOutlined,
  SearchOutlined,
  SettingOutlined,
  QuestionCircleOutlined,
  DownOutlined,
  RightOutlined,
  ReloadOutlined,
  DeleteOutlined
} from '@ant-design/icons';
import { conflictApi } from '../services/api';
import { ConflictList } from '../components_new/ConflictList';
import { ConflictDetailModal } from '../components_new/ConflictDetailModal';
import { EntitySnapshotViewer } from '../components_new/EntitySnapshotViewer';

const { Title, Text } = Typography;

interface Conflict {
  id: string;
  entityId: string;
  entityName: string;
  property: string;
  valueA: string;
  valueB: string;
  severity: 'critical' | 'warning' | 'info';
  status: string;
  description: string;
  aiSuggestion: string;
}

export const ConflictDetection: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const [loading, setLoading] = useState(false);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [selectedConflict, setSelectedConflict] = useState<Conflict | null>(null);
  const [entitySnapshots, setEntitySnapshots] = useState<any>(null);
  const [extractLoading, setExtractLoading] = useState(false);
  const [detectLoading, setDetectLoading] = useState(false);
  
  // 设置选项
  const [extractMode, setExtractMode] = useState<'incremental' | 'full'>('incremental');
  const [detectMode, setDetectMode] = useState<'incremental' | 'full'>('incremental');
  const [useExtractAI, setUseExtractAI] = useState(false);
  const [useDetectAI, setUseDetectAI] = useState(false);
  const [panelCollapsed, setPanelCollapsed] = useState(false);

  useEffect(() => {
    if (projectId) {
      loadConflicts();
    }
  }, [projectId]);

  const handleExtractEntities = async () => {
    if (!projectId) return;

    setExtractLoading(true);
    try {
      const params: any = { mode: extractMode };
      if (useExtractAI) {
        params.ai_provider = 'openai';
      }
      
      const response = await conflictApi.extractEntities(projectId, params);
      
      if (response.skipped > 0 && response.extracted === 0) {
        message.info(response.message);
      } else {
        message.success(
          `${response.message}：新增 ${response.extracted} 个设定` +
          (response.skipped > 0 ? `，跳过 ${response.skipped} 章` : '')
        );
      }
    } catch (error) {
      message.error('提取设定失败，请稍后重试');
    } finally {
      setExtractLoading(false);
    }
  };

  const handleDetectConflicts = async () => {
    if (!projectId) return;

    setDetectLoading(true);
    try {
      const params: any = {};
      if (detectMode === 'full') {
        params.clear_existing = true;
      }
      if (useDetectAI) {
        params.use_ai = true;
      }
      const response = await conflictApi.detectConflicts(projectId, params);
      const count = response.count;

      if (count > 0) {
        message.warning(`检测到 ${count} 个矛盾`);
        loadConflicts();
      } else {
        message.success('恭喜！未检测到矛盾');
      }
    } catch (error) {
      message.error('检测矛盾失败，请稍后重试');
    } finally {
      setDetectLoading(false);
    }
  };

  const loadConflicts = async () => {
    if (!projectId) return;

    setLoading(true);
    try {
      const response = await conflictApi.getConflicts(projectId);
      setConflicts(response.items || []);
    } catch (error) {
      message.error('加载矛盾列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleViewEntity = async (entityId: string, entityName: string) => {
    if (!projectId) return;

    try {
      const response = await conflictApi.getEntitySnapshots(projectId, entityId);
      setEntitySnapshots(response);
    } catch (error) {
      message.error('获取实体设定失败');
    }
  };

  const handleResolveConflict = async (conflictId: string, resolution: string) => {
    try {
      await conflictApi.resolveConflict(conflictId, resolution);
      message.success('矛盾标记为已解决');
      loadConflicts();
    } catch (error) {
      message.error('解决矛盾失败');
    }
  };

  const handleIgnoreConflict = async (conflictId: string) => {
    try {
      await conflictApi.ignoreConflict(conflictId);
      message.success('矛盾已忽略');
      loadConflicts();
    } catch (error) {
      message.error('忽略矛盾失败');
    }
  };

  const stats = {
    total: conflicts.length,
    critical: conflicts.filter(c => c.severity === 'critical').length,
    warning: conflicts.filter(c => c.severity === 'warning').length,
    info: conflicts.filter(c => c.severity === 'info').length,
  };

  return (
    <div style={{ 
      padding: '16px', 
      background: '#f0f2f5', 
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    }}>
      {/* 可折叠的控制面板 */}
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
              <BugOutlined /> 设定追溯与矛盾检测
            </Title>
            {panelCollapsed && (
              <Space size="large" style={{ marginLeft: 24 }}>
                <Text type="secondary">矛盾: {stats.total}</Text>
                {stats.critical > 0 && <Tag color="red">严重 {stats.critical}</Tag>}
                {stats.warning > 0 && <Tag color="orange">警告 {stats.warning}</Tag>}
              </Space>
            )}
          </Space>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {panelCollapsed ? '展开' : '收起'}
          </Text>
        </div>

        {/* 可折叠内容 */}
        {!panelCollapsed && (
          <>
            {/* 统计信息 */}
            <Row gutter={12} style={{ marginBottom: 12 }}>
              <Col xs={12} sm={6}>
                <Card size="small" bodyStyle={{ padding: '8px 12px' }}>
                  <Statistic title="总矛盾" value={stats.total} valueStyle={{ fontSize: 20 }} />
                </Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card size="small" bodyStyle={{ padding: '8px 12px' }}>
                  <Statistic 
                    title="严重" 
                    value={stats.critical} 
                    valueStyle={{ color: '#ff4d4f', fontSize: 20 }} 
                  />
                </Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card size="small" bodyStyle={{ padding: '8px 12px' }}>
                  <Statistic 
                    title="警告" 
                    value={stats.warning} 
                    valueStyle={{ color: '#faad14', fontSize: 20 }} 
                  />
                </Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card size="small" bodyStyle={{ padding: '8px 12px' }}>
                  <Statistic 
                    title="提示" 
                    value={stats.info} 
                    valueStyle={{ color: '#1890ff', fontSize: 20 }} 
                  />
                </Card>
              </Col>
            </Row>

            {/* 提取设定区域 */}
            <Card size="small" style={{ marginBottom: 12 }} title={<Text strong><SearchOutlined /> 提取设定</Text>}>
              <Row gutter={16} align="middle">
                <Col>
                  <Space>
                    <Text type="secondary">模式:</Text>
                    <Radio.Group 
                      value={extractMode} 
                      onChange={e => setExtractMode(e.target.value)}
                      size="small"
                      optionType="button"
                    >
                      <Radio.Button value="incremental">
                        <Tooltip title="只处理新增章节，速度快">增量</Tooltip>
                      </Radio.Button>
                      <Radio.Button value="full">
                        <Tooltip title="清空后重新提取所有章节">全量</Tooltip>
                      </Radio.Button>
                    </Radio.Group>
                  </Space>
                </Col>
                <Col>
                  <Space>
                    <Tooltip title="开启后使用AI提取（更准确但较慢，约20秒/章）">
                      <Space>
                        <Text type="secondary">AI提取:</Text>
                        <Switch 
                          checked={useExtractAI} 
                          onChange={setUseExtractAI}
                          size="small"
                        />
                      </Space>
                    </Tooltip>
                  </Space>
                </Col>
                <Col>
                  {extractMode === 'full' ? (
                    <Popconfirm
                      title="全量提取确认"
                      description="将清空现有设定数据并重新提取，确定继续？"
                      onConfirm={handleExtractEntities}
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button
                        type="primary"
                        icon={<ReloadOutlined />}
                        loading={extractLoading}
                        danger
                      >
                        全量提取
                      </Button>
                    </Popconfirm>
                  ) : (
                    <Button
                      type="primary"
                      icon={<SearchOutlined />}
                      loading={extractLoading}
                      onClick={handleExtractEntities}
                    >
                      增量提取
                    </Button>
                  )}
                </Col>
              </Row>
            </Card>

            {/* 检测矛盾区域 */}
            <Card size="small" title={<Text strong><BugOutlined /> 检测矛盾</Text>}>
              <Row gutter={16} align="middle">
                <Col>
                  <Space>
                    <Text type="secondary">模式:</Text>
                    <Radio.Group 
                      value={detectMode} 
                      onChange={e => setDetectMode(e.target.value)}
                      size="small"
                      optionType="button"
                    >
                      <Radio.Button value="incremental">
                        <Tooltip title="保留已有记录，只添加新检测到的矛盾">增量</Tooltip>
                      </Radio.Button>
                      <Radio.Button value="full">
                        <Tooltip title="清空已有矛盾记录后重新检测">重检</Tooltip>
                      </Radio.Button>
                    </Radio.Group>
                  </Space>
                </Col>
                <Col>
                  <Space>
                    <Tooltip title="开启后使用AI判断是否真的矛盾（更准确但较慢）">
                      <Space>
                        <Text type="secondary">AI检测:</Text>
                        <Switch 
                          checked={useDetectAI} 
                          onChange={setUseDetectAI}
                          size="small"
                        />
                      </Space>
                    </Tooltip>
                  </Space>
                </Col>
                <Col>
                  {detectMode === 'full' ? (
                    <Popconfirm
                      title="重新检测确认"
                      description="将清空现有矛盾记录后重新检测，确定继续？"
                      onConfirm={handleDetectConflicts}
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button
                        type="primary"
                        icon={<ReloadOutlined />}
                        loading={detectLoading}
                        danger
                      >
                        {useDetectAI ? 'AI重新检测' : '重新检测'}
                      </Button>
                    </Popconfirm>
                  ) : (
                    <Button
                      type="primary"
                      icon={<BugOutlined />}
                      loading={detectLoading}
                      onClick={handleDetectConflicts}
                    >
                      {useDetectAI ? 'AI检测矛盾' : '检测矛盾'}
                    </Button>
                  )}
                </Col>
                <Col flex="auto" style={{ textAlign: 'right' }}>
                  {useExtractAI && <Tag color="blue">AI提取</Tag>}
                  {useDetectAI && <Tag color="purple">AI检测</Tag>}
                  {detectMode === 'full' && <Tag color="red">清空重检</Tag>}
                  {!useExtractAI && !useDetectAI && detectMode !== 'full' && <Tag>规则模式</Tag>}
                </Col>
              </Row>
            </Card>
          </>
        )}
      </Card>

      {/* 矛盾列表 */}
      <Card
        title={<Text strong>矛盾列表 ({conflicts.length})</Text>}
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
          overflow: 'auto',
          padding: '0 12px 12px'
        }}
      >
        <ConflictList
          loading={loading}
          conflicts={conflicts}
          onViewDetail={setSelectedConflict}
          onViewEntity={handleViewEntity}
          onResolve={handleResolveConflict}
          onIgnore={handleIgnoreConflict}
        />
      </Card>

      {/* 矛盾详情弹窗 */}
      {selectedConflict && (
        <ConflictDetailModal
          conflict={selectedConflict}
          projectId={projectId!}
          visible={!!selectedConflict}
          onClose={() => setSelectedConflict(null)}
          onResolve={handleResolveConflict}
          onIgnore={handleIgnoreConflict}
        />
      )}

      {/* 实体设定查看弹窗 */}
      {entitySnapshots && (
        <EntitySnapshotViewer
          entitySnapshots={entitySnapshots}
          visible={!!entitySnapshots}
          onClose={() => setEntitySnapshots(null)}
        />
      )}
    </div>
  );
};
