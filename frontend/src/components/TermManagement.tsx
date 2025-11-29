import React, { useState, useEffect } from 'react';
import { Button, Modal, Form, Input, Table, Space, message, Popconfirm, Tooltip, Typography } from 'antd';
import { EditOutlined, DeleteOutlined, PlusOutlined, BookOutlined } from '@ant-design/icons';
import { useStore } from '../store';
import { termApi } from '../services/api';
import type { Term, TermCreate, TermUpdate } from '../types/index';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface TermManagementProps {
  projectId: string;
}

export const TermManagement: React.FC<TermManagementProps> = ({ projectId }) => {
  const { currentProject } = useStore();
  const [terms, setTerms] = useState<Term[]>([]);
  const [loading, setLoading] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingTerm, setEditingTerm] = useState<Term | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    if (projectId) {
      loadTerms();
    }
  }, [projectId]);

  const loadTerms = async () => {
    setLoading(true);
    try {
      const response = await termApi.getProjectTerms(projectId);
      setTerms(response.items);
    } catch (error) {
      message.error('加载词条失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAddTerm = () => {
    setEditingTerm(null);
    form.resetFields();
    setIsModalVisible(true);
  };

  const handleEditTerm = (term: Term) => {
    setEditingTerm(term);
    form.setFieldsValue(term);
    setIsModalVisible(true);
  };

  const handleDeleteTerm = async (termId: string) => {
    try {
      await termApi.deleteTerm(termId);
      message.success('词条删除成功');
      loadTerms();
    } catch (error) {
      message.error('删除词条失败');
    }
  };

  const handleSaveTerm = async (values: TermCreate | TermUpdate) => {
    try {
      if (editingTerm) {
        await termApi.updateTerm(editingTerm.id, values as TermUpdate);
        message.success('词条更新成功');
      } else {
        await termApi.createTerm({ ...values as TermCreate, project_id: projectId });
        message.success('词条创建成功');
      }
      setIsModalVisible(false);
      form.resetFields();
      loadTerms();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '保存词条失败');
    }
  };

  const columns = [
    {
      title: '词条名称',
      dataIndex: 'name',
      key: 'name',
      sorter: (a: Term, b: Term) => a.name.localeCompare(b.name),
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (text: string) => <Tooltip title={text} placement="topLeft"><Paragraph ellipsis={{ rows: 2 }}>{text}</Paragraph></Tooltip>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      sorter: (a: Term, b: Term) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: Term) => (
        <Space size="middle">
          <Button
            icon={<EditOutlined />}
            onClick={() => handleEditTerm(record)}
            type="link"
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除此词条吗？"
            description="删除后，章节内容中通过此词条高亮的功能将失效。"
            onConfirm={() => handleDeleteTerm(record.id)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button icon={<DeleteOutlined />} type="link" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3><BookOutlined /> 项目百科词条管理</h3>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAddTerm}>
          添加新词条
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={terms}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
        scroll={{ x: 'max-content' }}
      />

      <Modal
        title={editingTerm ? '编辑词条' : '添加词条'}
        open={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        footer={null}
        centered
      >
        <Form form={form} layout="vertical" onFinish={handleSaveTerm}>
          <Form.Item
            name="name"
            label="词条名称"
            rules={[{ required: true, message: '请输入词条名称' }, { max: 200, message: '词条名称最长200个字符' }]} 
          >
            <Input placeholder="例如：虚空之剑、艾莉丝公主" />
          </Form.Item>
          <Form.Item
            name="description"
            label="详细描述"
            rules={[{ max: 1000, message: '描述最长1000个字符' }]} // 限制描述长度
          >
            <TextArea rows={4} placeholder="例如：一把拥有切割空间能力的传说武器。艾莉丝是帝国的三公主，性格活泼开朗..." />
          </Form.Item>
          <Form.Item>
            <Space style={{ float: 'right' }}>
              <Button onClick={() => setIsModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit">
                保存
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
