import React, { useState, useEffect } from 'react';
import { Modal, List, Button, Tag, Space, Typography, message, Popconfirm, Drawer, Spin } from 'antd';
import { HistoryOutlined, RollbackOutlined, EyeOutlined, ClockCircleOutlined, UserOutlined, RobotOutlined } from '@ant-design/icons';
import { versionApi } from '../services/api';

const { Text, Paragraph } = Typography;

interface ChapterVersion {
  id: string;
  version_number: number;
  word_count: number;
  source: string;
  created_at: string;
  ai_provider?: string;
  ai_model?: string;
  preview: string;
}

interface VersionDetail {
  id: string;
  version_number: number;
  content: string;
  word_count: number;
  source: string;
  created_at: string;
}

interface ChapterHistoryModalProps {
  chapterId: string;
  visible: boolean;
  onClose: () => void;
  onRestoreSuccess: () => void;
}

export const ChapterHistoryModal: React.FC<ChapterHistoryModalProps> = ({
  chapterId,
  visible,
  onClose,
  onRestoreSuccess
}) => {
  const [loading, setLoading] = useState(false);
  const [versions, setVersions] = useState<ChapterVersion[]>([]);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewVersion, setPreviewVersion] = useState<VersionDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [restoring, setRestoring] = useState<string | null>(null);

  useEffect(() => {
    if (visible && chapterId) {
      loadVersions();
    }
  }, [visible, chapterId]);

  const loadVersions = async () => {
    setLoading(true);
    try {
      const response: any = await versionApi.getVersions(chapterId);
      setVersions(response.versions || []);
    } catch (error) {
      message.error('加载版本历史失败');
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async (versionId: string) => {
    setPreviewLoading(true);
    setPreviewVisible(true);
    try {
      const response: any = await versionApi.getVersionDetail(chapterId, versionId);
      setPreviewVersion(response);
    } catch (error) {
      message.error('加载版本详情失败');
      setPreviewVisible(false);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleRestore = async (versionId: string) => {
    setRestoring(versionId);
    try {
      await versionApi.restoreVersion(chapterId, versionId);
      message.success('版本恢复成功');
      onRestoreSuccess();
      onClose(); // 恢复成功后关闭历史记录窗口
    } catch (error) {
      message.error('恢复版本失败');
    } finally {
      setRestoring(null);
    }
  };

  const getSourceTag = (source: string) => {
    switch (source) {
      case 'user':
        return <Tag icon={<UserOutlined />} color="blue">手动编辑</Tag>;
      case 'ai':
        return <Tag icon={<RobotOutlined />} color="purple">AI生成</Tag>;
      case 'restore':
        return <Tag icon={<RollbackOutlined />} color="orange">版本恢复</Tag>;
      default:
        return <Tag>{source}</Tag>;
    }
  };

  return (
    <>
      <Modal
        title={
          <Space>
            <HistoryOutlined />
            <span>历史版本记录</span>
          </Space>
        }
        open={visible}
        onCancel={onClose}
        footer={[
          <Button key="close" onClick={onClose}>
            关闭
          </Button>
        ]}
        width={800}
      >
        <List
          loading={loading}
          dataSource={versions}
          renderItem={(item) => (
            <List.Item
              actions={[
                <Button 
                  key="preview" 
                  type="link" 
                  icon={<EyeOutlined />} 
                  onClick={() => handlePreview(item.id)}
                >
                  预览
                </Button>,
                <Popconfirm
                  key="restore"
                  title="确认恢复此版本？"
                  description="当前未保存的内容将会作为新版本自动备份。"
                  onConfirm={() => handleRestore(item.id)}
                  okText="恢复"
                  cancelText="取消"
                >
                  <Button 
                    type="link" 
                    danger 
                    icon={<RollbackOutlined />}
                    loading={restoring === item.id}
                  >
                    恢复
                  </Button>
                </Popconfirm>
              ]}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <Text strong>V{item.version_number}</Text>
                    {getSourceTag(item.source)}
                    <Text type="secondary" style={{ fontSize: '12px' }}>
                      <ClockCircleOutlined /> {new Date(item.created_at).toLocaleString()}
                    </Text>
                  </Space>
                }
                description={
                  <Space direction="vertical" style={{ width: '100%' }} size={2}>
                    <Text type="secondary">字数: {item.word_count}</Text>
                    {item.ai_model && (
                      <Text type="secondary" style={{ fontSize: '12px' }}>
                        模型: {item.ai_model}
                      </Text>
                    )}
                    <Text style={{ color: '#666', fontSize: '13px' }} ellipsis>
                      {item.preview}
                    </Text>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      </Modal>

      <Drawer
        title={previewVersion ? `预览版本 V${previewVersion.version_number}` : '版本预览'}
        width="60%"
        onClose={() => setPreviewVisible(false)}
        open={previewVisible}
        extra={
          previewVersion && (
            <Popconfirm
              title="确认恢复此版本？"
              description="当前未保存的内容将会作为新版本自动备份。"
              onConfirm={() => handleRestore(previewVersion.id)}
              okText="恢复"
              cancelText="取消"
            >
              <Button 
                type="primary" 
                danger 
                icon={<RollbackOutlined />}
                loading={restoring === previewVersion.id}
              >
                恢复此版本
              </Button>
            </Popconfirm>
          )
        }
      >
        {previewLoading ? (
          <div style={{ textAlign: 'center', padding: '50px' }}>
            <Spin tip="加载内容中..." />
          </div>
        ) : previewVersion ? (
          <div>
            <div style={{ marginBottom: 16, padding: 12, background: '#f5f5f5', borderRadius: 4 }}>
              <Space split="|">
                <Text>字数: {previewVersion.word_count}</Text>
                <Text>来源: {previewVersion.source}</Text>
                <Text>时间: {new Date(previewVersion.created_at).toLocaleString()}</Text>
              </Space>
            </div>
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, fontSize: 16 }}>
              {previewVersion.content}
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', color: '#999' }}>无法加载预览</div>
        )}
      </Drawer>
    </>
  );
};
