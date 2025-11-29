import React from 'react';
import { useParams } from 'react-router-dom';
import { Card, Typography, message } from 'antd';
import { TermManagement } from '../components/TermManagement';
import { BookOutlined } from '@ant-design/icons';

const { Title, Paragraph } = Typography;

export default function ProjectWiki() {
  const { projectId } = useParams<{ projectId: string }>();

  if (!projectId) {
    message.error('项目ID缺失，无法管理百科词条。');
    return (
      <Card style={{ margin: 24 }}>
        <Title level={4}><BookOutlined /> 项目百科</Title>
        <Paragraph type="danger">无法加载项目百科，请确保您从有效的项目页面进入。</Paragraph>
      </Card>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <TermManagement projectId={projectId} />
    </div>
  );
}
