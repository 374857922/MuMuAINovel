import React from 'react';
import { Modal, Descriptions, Tag, Typography, Timeline, Card, Space, Button } from 'antd';
import { HistoryOutlined, TagsOutlined } from '@ant-design/icons';

const { Text, Paragraph } = Typography;

interface EntitySnapshot {
  id: string;
  value: string;
  sourceChapterId: string;
  quote: string;
  confidence: number;
  createdAt: string;
}

interface PropertySnapshots {
  propertyName: string;
  displayName: string;
  snapshots: EntitySnapshot[];
  hasConflict: boolean;
  conflictStatus: string;
}

interface EntitySnapshots {
  entityId: string;
  entityName: string;
  entityType: string;
  properties: PropertySnapshots[];
}

interface EntitySnapshotViewerProps {
  entitySnapshots: EntitySnapshots;
  visible: boolean;
  onClose: () => void;
}

export const EntitySnapshotViewer: React.FC<EntitySnapshotViewerProps> = ({
  entitySnapshots,
  visible,
  onClose
}) => {
  return (
    <Modal
      title={
        <>
          <HistoryOutlined /> 设定追溯 - {entitySnapshots.entityName}
        </>
      }
      open={visible}
      onCancel={onClose}
      width={900}
      footer={
        <Button onClick={onClose}>关闭</Button>
      }
    >
      <Card
        title={
          <Space>
            <TagsOutlined />
            <Text strong>{entitySnapshots.entityName}</Text>
            <Tag color="blue">{entitySnapshots.entityType}</Tag>
          </Space>
        }
        style={{ marginBottom: '16px' }}
      >
        <Descriptions column={2}>
          <Descriptions.Item label="实体ID">
            <Text copyable>{entitySnapshots.entityId}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="属性数量">
            {entitySnapshots.properties.length}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {entitySnapshots.properties.map((property) => (
        <Card
          key={property.propertyName}
          title={
            <Space>
              <Text strong style={{ color: property.hasConflict ? '#faad14' : '#52c41a' }}>
                {property.displayName}
              </Text>
              {property.hasConflict && (
                <Tag color="orange">
                  有矛盾 ({property.conflictStatus})
                </Tag>
              )}
              {!property.hasConflict && (
                <Tag color="green">一致</Tag>
              )}
            </Space>
          }
          style={{ marginBottom: '16px' }}
          size="small"
        >
          <Timeline>
            {property.snapshots.map((snapshot, index) => (
              <Timeline.Item key={snapshot.id}>
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  <Text strong>{snapshot.value}</Text>
                  {snapshot.quote && (
                    <Paragraph
                      style={{
                        background: '#f0f0f0',
                        padding: '8px',
                        borderRadius: '4px',
                        borderLeft: '3px solid #1890ff',
                        marginBottom: '8px'
                      }}
                    >
                      {snapshot.quote}
                    </Paragraph>
                  )}
                  <Space size="large">
                    <Text type="secondary" style={{ fontSize: '12px' }}>
                      来源章节: {snapshot.sourceChapterId}
                    </Text>
                    <Text type="secondary" style={{ fontSize: '12px' }}>
                      置信度: {(snapshot.confidence * 100).toFixed(0)}%
                    </Text>
                    <Text type="secondary" style={{ fontSize: '12px' }}>
                      {new Date(snapshot.createdAt).toLocaleDateString()}
                    </Text>
                  </Space>
                </Space>
              </Timeline.Item>
            ))}
          </Timeline>
        </Card>
      ))}
    </Modal>
  );
};
