import React from 'react';
import { Table, Tag, Button, Space, Popconfirm, Typography, Tooltip } from 'antd';
import {
  EyeOutlined,
  UserOutlined,
  CheckOutlined,
  CloseOutlined
} from '@ant-design/icons';

const { Text } = Typography;

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

interface ConflictListProps {
  loading: boolean;
  conflicts: Conflict[];
  onViewDetail: (conflict: Conflict) => void;
  onViewEntity: (entityId: string, entityName: string) => void;
  onResolve: (conflictId: string, resolution: string) => void;
  onIgnore: (conflictId: string) => void;
}

export const ConflictList: React.FC<ConflictListProps> = ({
  loading,
  conflicts,
  onViewDetail,
  onViewEntity,
  onResolve,
  onIgnore
}) => {
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'red';
      case 'warning': return 'orange';
      case 'info': return 'blue';
      default: return 'default';
    }
  };

  const getSeverityText = (severity: string) => {
    switch (severity) {
      case 'critical': return '严重';
      case 'warning': return '警告';
      case 'info': return '提示';
      default: return '未知';
    }
  };

  const columns = [
    {
      title: '实体',
      dataIndex: 'entityName',
      key: 'entityName',
      width: 100,
      ellipsis: true,
      render: (text: string, record: Conflict) => (
        <Tooltip title={`查看 ${text || '实体'} 的所有设定`}>
          <Button
            type="link"
            size="small"
            style={{ padding: 0 }}
            onClick={() => onViewEntity(record.entityId, record.entityName)}
          >
            <UserOutlined /> {text || '未知'}
          </Button>
        </Tooltip>
      ),
    },
    {
      title: '属性',
      dataIndex: 'property',
      key: 'property',
      width: 80,
      ellipsis: true,
    },
    {
      title: '冲突内容',
      key: 'conflict',
      width: 240,
      render: (_: any, record: Conflict) => (
        <div style={{ fontSize: 12 }}>
          <div style={{ marginBottom: 4 }}>
            <Text type="secondary">A: </Text>
            <Tooltip title={record.valueA}>
              <Text ellipsis style={{ maxWidth: 180, display: 'inline-block', verticalAlign: 'bottom' }}>
                {record.valueA}
              </Text>
            </Tooltip>
          </div>
          <div>
            <Text type="secondary">B: </Text>
            <Tooltip title={record.valueB}>
              <Text ellipsis style={{ maxWidth: 180, display: 'inline-block', verticalAlign: 'bottom' }}>
                {record.valueB}
              </Text>
            </Tooltip>
          </div>
        </div>
      ),
    },
    {
      title: '级别',
      dataIndex: 'severity',
      key: 'severity',
      width: 70,
      render: (severity: string) => (
        <Tag color={getSeverityColor(severity)} style={{ margin: 0 }}>
          {getSeverityText(severity)}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 70,
      render: (status: string) => {
        const statusMap: Record<string, string> = {
          detected: '待处理',
          verified: '已确认',
          resolved: '已解决',
          ignored: '已忽略'
        };
        const colorMap: Record<string, string> = {
          detected: 'processing',
          verified: 'cyan',
          resolved: 'success',
          ignored: 'default'
        };
        return (
          <Tag color={colorMap[status] || 'default'} style={{ margin: 0 }}>
            {statusMap[status] || status}
          </Tag>
        );
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      fixed: 'right' as const,
      render: (_: any, record: Conflict) => (
        <Space size={4}>
          <Button
            type="primary"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => onViewDetail(record)}
          >
            详情
          </Button>

          {record.status === 'detected' && (
            <>
              <Popconfirm
                title="确认解决"
                description="确认已经解决了这个矛盾？"
                onConfirm={() => onResolve(record.id, '已解决')}
                okText="是"
                cancelText="否"
              >
                <Button
                  type="text"
                  size="small"
                  icon={<CheckOutlined />}
                  style={{ color: '#52c41a' }}
                />
              </Popconfirm>

              <Popconfirm
                title="确认忽略"
                description="确认这不是真正的矛盾？"
                onConfirm={() => onIgnore(record.id)}
                okText="是"
                cancelText="否"
              >
                <Button
                  type="text"
                  size="small"
                  icon={<CloseOutlined />}
                  style={{ color: '#8c8c8c' }}
                />
              </Popconfirm>
            </>
          )}
        </Space>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={conflicts}
      rowKey="id"
      loading={loading}
      size="small"
      scroll={{ x: 800 }}
      pagination={{
        size: 'small',
        pageSize: 10,
        showSizeChanger: true,
        pageSizeOptions: ['10', '20', '50'],
        showTotal: (total, range) => `${range[0]}-${range[1]} / ${total}`,
        style: { marginBottom: 0, padding: '8px 0' }
      }}
      locale={{
        emptyText: '暂无矛盾，请先提取设定并检测',
      }}
    />
  );
};
