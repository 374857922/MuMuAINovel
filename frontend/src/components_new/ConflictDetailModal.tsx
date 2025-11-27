import React, { useState, useEffect } from 'react';
import {
  Modal,
  Descriptions,
  Tag,
  Typography,
  Space,
  Button,
  Input,
  Timeline,
  Card,
  Row,
  Col,
  Spin,
  Alert
} from 'antd';
import {
  CheckOutlined,
  CloseOutlined,
  UserOutlined,
  FileTextOutlined,
  RobotOutlined,
  SolutionOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons';
import { conflictApi } from '../services/api';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

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

interface ConflictDetail {
  entity: {
    id: string;
    name: string;
    type: string;
  };
  property: {
    name: string;
    displayName: string;
  };
  snapshotA: {
    value: string;
    sourceChapterId: string;
    quote: string;
    context: string;
  };
  snapshotB: {
    value: string;
    sourceChapterId: string;
    quote: string;
    context: string;
  };
  conflict: {
    type: string;
    severity: string;
    description: string;
    detectedAt: string;
    status: string;
  };
  aiSuggestion: string;
}

interface ConflictDetailModalProps {
  conflict: Conflict;
  projectId: string;
  visible: boolean;
  onClose: () => void;
  onResolve: (conflictId: string, resolution: string) => void;
  onIgnore: (conflictId: string) => void;
}

export const ConflictDetailModal: React.FC<ConflictDetailModalProps> = ({
  conflict,
  projectId,
  visible,
  onClose,
  onResolve,
  onIgnore
}) => {
  const [detail, setDetail] = useState<ConflictDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [resolution, setResolution] = useState('');

  useEffect(() => {
    if (visible && conflict) {
      loadDetail();
    }
  }, [visible, conflict]);

  const loadDetail = async () => {
    setLoading(true);
    try {
      const response = await conflictApi.getConflictDetail(conflict.id);
      setDetail(response);
    } catch (error) {
      console.error('加载矛盾详情失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = () => {
    if (!resolution.trim()) {
      Modal.warning({
        title: '请输入解决方案',
        content: '请说明如何解决这个矛盾（例如：修订了第3章的设定，将年龄改为20岁）'
      });
      return;
    }

    onResolve(conflict.id, resolution);
    onClose();
  };

  const handleIgnore = () => {
    Modal.confirm({
      title: '确认忽略矛盾',
      content: '确认这不是真正的矛盾吗？',
      onOk: () => {
        onIgnore(conflict.id);
        onClose();
      }
    });
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return '#ff4d4f';
      case 'warning': return '#faad14';
      case 'info': return '#1890ff';
      default: return '#8c8c8c';
    }
  };

  return (
    <Modal
      title={
        <Space>
          <ExclamationCircleOutlined style={{ color: '#faad14' }} />
          <Title level={4} style={{ margin: 0 }}>矛盾详情</Title>
        </Space>
      }
      open={visible}
      onCancel={onClose}
      width={800}
      footer={
        conflict.status === 'detected' ? (
          <Space>
            <Button onClick={onClose}>取消</Button>
            <Button
              type="primary"
              icon={<CheckOutlined />}
              onClick={handleResolve}
            >
              标记为已解决
            </Button>
            <Button
              danger
              icon={<CloseOutlined />}
              onClick={handleIgnore}
            >
              忽略矛盾
            </Button>
          </Space>
        ) : (
          <Button onClick={onClose}>关闭</Button>
        )
      }
    >
      <Spin spinning={loading}>
        {detail && (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Card
              title={<Space><UserOutlined />实体信息</Space>}
              size="small"
            >
              <Descriptions column={2}>
                <Descriptions.Item label="实体名称">
                  <Text strong>{detail.entity.name || '未知实体'}</Text>
                </Descriptions.Item>
                <Descriptions.Item label="实体类型">
                  <Tag color="blue">{detail.entity.type}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="属性">
                  <Text strong style={{ color: '#1890ff' }}>
                    {detail.property.displayName}
                  </Text>
                </Descriptions.Item>
              </Descriptions>
            </Card>

            <Card
              title={<Space><FileTextOutlined />设定对比</Space>}
              size="small"
            >
              <Row gutter={16}>
                <Col span={12}>
                  <Card
                    title={<Text type="success">设定A（来源章节）</Text>}
                    size="small"
                    style={{ background: '#f6ffed', borderColor: '#b7eb8f' }}
                  >
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <Text strong>{detail.snapshotA.value}</Text>
                      {detail.snapshotA.quote && (
                        <div>
                          <Text type="secondary">原文引用：</Text>
                          <Paragraph
                            style={{
                              background: '#fff',
                              padding: '8px',
                              borderRadius: '4px',
                              borderLeft: '3px solid #52c41a'
                            }}
                          >
                            "{detail.snapshotA.quote}"
                          </Paragraph>
                        </div>
                      )}
                    </Space>
                  </Card>
                </Col>
                <Col span={12}>
                  <Card
                    title={<Text type="danger">设定B（来源章节）</Text>}
                    size="small"
                    style={{ background: '#fff2e8', borderColor: '#ffccc7' }}
                  >
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <Text strong>{detail.snapshotB.value}</Text>
                      {detail.snapshotB.quote && (
                        <div>
                          <Text type="secondary">原文引用：</Text>
                          <Paragraph
                            style={{
                              background: '#fff',
                              padding: '8px',
                              borderRadius: '4px',
                              borderLeft: '3px solid #ff4d4f'
                            }}
                          >
                            "{detail.snapshotB.quote}"
                          </Paragraph>
                        </div>
                      )}
                    </Space>
                  </Card>
                </Col>
              </Row>
            </Card>

            <Card
              title={
                <Space>
                  <ExclamationCircleOutlined style={{ color: getSeverityColor(detail.conflict.severity) }} />
                  矛盾信息
                </Space>
              }
              size="small"
            >
              <Alert
                message={
                  <Space>
                    <Text>严重程度：</Text>
                    <Tag color={getSeverityColor(detail.conflict.severity)}>
                      {detail.conflict.severity.toUpperCase()}
                    </Tag>
                  </Space>
                }
                description={detail.conflict.description}
                type="warning"
                showIcon
                style={{ marginBottom: '16px' }}
              />
              <Text type="secondary">检测时间：{new Date(detail.conflict.detectedAt).toLocaleString()}</Text>
            </Card>

            <Card
              title={<Space><RobotOutlined />AI建议</Space>}
              size="small"
              style={{ background: '#f0f5ff', borderColor: '#adc6ff' }}
            >
              <Timeline>
                {detail.aiSuggestion.split('|').map((suggestion, index) => (
                  <Timeline.Item key={index} dot={<SolutionOutlined />}>
                    {suggestion.trim()}
                  </Timeline.Item>
                ))}
              </Timeline>
            </Card>

            {conflict.status === 'detected' && (
              <Card
                title="解决方案"
                size="small"
              >
                <TextArea
                  rows={3}
                  placeholder="请描述如何解决这个矛盾（例如：修订了第3章的设定，将年龄改为20岁）"
                  value={resolution}
                  onChange={(e) => setResolution(e.target.value)}
                />
              </Card>
            )}

            {conflict.status !== 'detected' && (
              <Card
                title={<Text type="success">处理状态</Text>}
                size="small"
              >
                <Text strong>{conflict.status === 'resolved' ? '✅ 已解决' : '⏭️ 已忽略'}</Text>
              </Card>
            )}
          </Space>
        )}
      </Spin>
    </Modal>
  );
};
