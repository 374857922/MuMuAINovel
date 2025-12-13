import { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate, Outlet, Link, useLocation } from 'react-router-dom';
import { Layout, Menu, Spin, Button, Statistic, Row, Col, Card, Drawer, Modal, Space, Input, message, List, Empty, Tag, Tooltip } from 'antd';
import {
  ArrowLeftOutlined,
  FileTextOutlined,
  TeamOutlined,
  BookOutlined,
  // ToolOutlined,
  GlobalOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  ApartmentOutlined,
  BankOutlined,
  EditOutlined,
  FundOutlined,
  BugOutlined,
  RadarChartOutlined,
  ClockCircleOutlined,
  LineChartOutlined,
} from '@ant-design/icons';
import { useStore } from '../store';
import { useCharacterSync, useOutlineSync, useChapterSync } from '../store/hooks';
import { projectApi } from '../services/api';
import api from '../services/api';

const { Header, Sider, Content } = Layout;

// 判断是否为移动端
const isMobile = () => window.innerWidth <= 768;

export default function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [mobile, setMobile] = useState(isMobile());
  // 监听窗口大小变化
  useEffect(() => {
    const handleResize = () => {
      setMobile(isMobile());
      if (!isMobile()) {
        setDrawerVisible(false);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);
  const {
    currentProject,
    setCurrentProject,
    clearProjectData,
    loading,
    setLoading,
    outlines,
    characters,
    chapters,
  } = useStore();

  // 使用同步 hooks
  const { refreshCharacters } = useCharacterSync();
  const { refreshOutlines } = useOutlineSync();
  const { refreshChapters } = useChapterSync();

  useEffect(() => {
    const loadProjectData = async (id: string) => {
      try {
        setLoading(true);
        // 加载项目基本信息
        const project = await projectApi.getProject(id);
        setCurrentProject(project);
        
        // 并行加载其他数据
        await Promise.all([
          refreshOutlines(id),
          refreshCharacters(id),
          refreshChapters(id),
        ]);
      } catch (error) {
        console.error('加载项目数据失败:', error);
      } finally {
        setLoading(false);
      }
    };

    if (projectId) {
      loadProjectData(projectId);
    }

    return () => {
      clearProjectData();
    };
  }, [projectId, clearProjectData, setLoading, setCurrentProject, refreshOutlines, refreshCharacters, refreshChapters]);

  // 移除事件监听，避免无限循环
  // Hook 内部已经更新了 store，不需要再次刷新

  const menuItems = [
    {
      key: 'world-setting',
      icon: <GlobalOutlined />,
      label: <Link to={`/project/${projectId}/world-setting`}>世界设定</Link>,
    },
    {
      key: 'characters',
      icon: <TeamOutlined />,
      label: <Link to={`/project/${projectId}/characters`}>角色管理</Link>,
    },
    {
      key: 'relationships',
      icon: <ApartmentOutlined />,
      label: <Link to={`/project/${projectId}/relationships`}>关系管理</Link>,
    },
    {
      key: 'organizations',
      icon: <BankOutlined />,
      label: <Link to={`/project/${projectId}/organizations`}>组织管理</Link>,
    },
    {
      key: 'outline',
      icon: <FileTextOutlined />,
      label: <Link to={`/project/${projectId}/outline`}>大纲管理</Link>,
    },
    {
      key: 'chapters',
      icon: <BookOutlined />,
      label: <Link to={`/project/${projectId}/chapters`}>章节管理</Link>,
    },
    {
      key: 'chapter-analysis',
      icon: <FundOutlined />,
      label: <Link to={`/project/${projectId}/chapter-analysis`}>剧情分析</Link>,
    },
    {
      key: 'conflict-detection',
      icon: <BugOutlined />,
      label: <Link to={`/project/${projectId}/conflict-detection`}>矛盾检测</Link>,
    },
    {
      key: 'chapter-graph',
      icon: <RadarChartOutlined />,
      label: <Link to={`/project/${projectId}/chapter-graph`}>章节图谱</Link>,
    },
    {
      key: 'writing-styles',
      icon: <EditOutlined />,
      label: <Link to={`/project/${projectId}/writing-styles`}>写作风格</Link>,
    },
    {
      key: 'pattern-analysis',
      icon: <LineChartOutlined />,
      label: <Link to={`/project/${projectId}/pattern-analysis`}>套路化分析</Link>,
    },
    {
      key: 'wiki',
      icon: <BookOutlined />,
      label: <Link to={`/project/${projectId}/wiki`}>项目百科</Link>,
    },
    {
      type: 'divider' as const,
      style: { margin: '8px 0' },
    },
  ];

  // 根据当前路径动态确定选中的菜单项
  const selectedKey = useMemo(() => {
    const path = location.pathname;
    if (path.includes('/world-setting')) return 'world-setting';
    if (path.includes('/relationships')) return 'relationships';
    if (path.includes('/organizations')) return 'organizations';
    if (path.includes('/outline')) return 'outline';
    if (path.includes('/chapters')) return 'chapters';
    if (path.includes('/characters')) return 'characters';
    if (path.includes('/chapter-analysis')) return 'chapter-analysis';
    if (path.includes('/conflict-detection')) return 'conflict-detection';
    if (path.includes('/chapter-graph')) return 'chapter-graph';
    if (path.includes('/writing-styles')) return 'writing-styles';
    if (path.includes('/pattern-analysis')) return 'pattern-analysis';
    if (path.includes('/wiki')) return 'wiki'; // 新增百科词条选中逻辑
    return 'outline';
  }, [location.pathname]);

  if (loading || !currentProject) {
    return (
      <Layout style={{
        height: '100vh',
        background: 'linear-gradient(135deg, #0f172a, #1e293b)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <Spin size="large" tip="加载项目中..." fullscreen />
      </Layout>
    );
  }

  return (
    <Layout style={{
      height: '100vh',
      background: 'linear-gradient(135deg, #0f172a, #1e293b)',
      overflow: 'hidden'
    }}>
      <Header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        height: mobile ? 56 : 70,
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        paddingLeft: mobile ? '12px' : '24px',
        paddingRight: mobile ? '12px' : '24px',
        backdropFilter: 'blur(10px)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', zIndex: 1 }}>
          <Button
            type="text"
            icon={mobile ? <MenuUnfoldOutlined /> : (collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />)}
            onClick={() => mobile ? setDrawerVisible(true) : setCollapsed(!collapsed)}
            style={{
              fontSize: mobile ? '18px' : '20px',
              color: '#fff',
              width: mobile ? '36px' : '40px',
              height: mobile ? '36px' : '40px'
            }}
          />
          {!mobile && (
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate('/')}
              style={{
                fontSize: '16px',
                color: '#fff',
                height: '40px',
                padding: '0 16px'
              }}
            >
              返回主页
            </Button>
          )}
        </div>

        <h2 style={{
          margin: 0,
          color: '#fff',
          fontSize: mobile ? '16px' : '24px',
          fontWeight: 600,
          textShadow: '0 2px 4px rgba(0,0,0,0.1)',
          position: mobile ? 'static' : 'absolute',
          left: mobile ? 'auto' : '50%',
          transform: mobile ? 'none' : 'translateX(-50%)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          maxWidth: mobile ? '200px' : '400px',
          textAlign: 'center'
        }}>{currentProject.title}</h2>

        {!mobile && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', zIndex: 1 }}>
            <Row gutter={12} style={{ width: 450, justifyContent: 'flex-end' }}>
              <Col>
                <Card size="small" variant="borderless" styles={{ body: { padding: 8 } }} style={{ background: 'rgba(255,255,255,0.95)', borderRadius: 6, minWidth: 80, textAlign: 'center' }}>
                  <Statistic 
                    title={<span style={{ fontSize: 11, color: '#666' }}>大纲</span>}
                    value={outlines.length} 
                    suffix="条"
                    valueStyle={{ fontSize: 16, fontWeight: 600, color: '#667eea' }} 
                  />
                </Card>
              </Col>
              <Col>
                <Card size="small" variant="borderless" styles={{ body: { padding: 8 } }} style={{ background: 'rgba(255,255,255,0.95)', borderRadius: 6, minWidth: 80, textAlign: 'center' }}>
                  <Statistic 
                    title={<span style={{ fontSize: 11, color: '#666' }}>角色</span>}
                    value={characters.length} 
                    suffix="个"
                    valueStyle={{ fontSize: 16, fontWeight: 600, color: '#52c41a' }} 
                  />
                </Card>
              </Col>
              <Col>
                <Card size="small" variant="borderless" styles={{ body: { padding: 8 } }} style={{ background: 'rgba(255,255,255,0.95)', borderRadius: 6, minWidth: 80, textAlign: 'center' }}>
                  <Statistic 
                    title={<span style={{ fontSize: 11, color: '#666' }}>章节</span>}
                    value={chapters.length} 
                    suffix="章"
                    valueStyle={{ fontSize: 16, fontWeight: 600, color: '#1890ff' }} 
                  />
                </Card>
              </Col>
              <Col>
                <Card size="small" variant="borderless" styles={{ body: { padding: 8 } }} style={{ background: 'rgba(255,255,255,0.95)', borderRadius: 6, minWidth: 80, textAlign: 'center' }}>
                  <Statistic 
                    title={<span style={{ fontSize: 11, color: '#666' }}>已写</span>}
                    value={currentProject.current_words} 
                    suffix="字"
                    valueStyle={{ fontSize: 16, fontWeight: 600, color: '#fa8c16' }} 
                  />
                </Card>
              </Col>
            </Row>
          </div>
        )}
      </Header>

      <Layout style={{ 
        height: '100vh', 
        overflow: 'hidden', 
        paddingTop: mobile ? 56 : 86 
      }}>
        {!mobile ? (
          <Sider
            width={collapsed ? 60 : 220}
            collapsed={collapsed}
            collapsible
            trigger={null}
            style={{
              backgroundColor: 'transparent',
              boxShadow: mobile ? 'none' : '2px 0 8px rgba(0,0,0,0.05)',
              overflow: 'hidden',
              marginLeft: 24,
              borderRadius: 8,
              height: 'calc(100% - 24px)'
            }}
          >
            <Menu
              mode="inline"
              theme="light"
              selectedKeys={[selectedKey]}
              items={menuItems}
              inlineCollapsed={collapsed}
              style={{ borderRight: 0, height: '100%', borderRadius: 8 }}
              onClick={() => mobile && setDrawerVisible(false)}
            />
          </Sider>
        ) : (
          <Drawer
            title="菜单"
            placement="left"
            open={drawerVisible}
            onClose={() => setDrawerVisible(false)}
            style={{ zIndex: 9999 }}
          >
            <Menu
              mode="inline"
              theme="light"
              selectedKeys={[selectedKey]}
              items={menuItems}
              style={{ borderRight: 0 }}
              onClick={() => setDrawerVisible(false)}
            />
          </Drawer>
        )}

        <Layout
          style={{
            transition: 'all 0.2s',
            backgroundColor: 'transparent'
          }}
        >
          <Content
            style={{
              background: 'transparent',
              padding: mobile ? 12 : '0 24px 24px 24px',
              height: '100%',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column'
            }}
          >
            <div style={{
              background: '#fff',
              padding: mobile ? 12 : 24,
              borderRadius: mobile ? '8px' : '12px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
              height: '100%',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column'
            }}>
              <Outlet />
            </div>
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
}