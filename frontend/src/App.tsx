import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import ProjectList from './pages/ProjectList';
import ProjectWizardNew from './pages/ProjectWizardNew';
import Inspiration from './pages/Inspiration';
import ProjectDetail from './pages/ProjectDetail';
import WorldSetting from './pages/WorldSetting';
import Outline from './pages/Outline';
import Characters from './pages/Characters';
import Relationships from './pages/Relationships';
import Organizations from './pages/Organizations';
import Chapters from './pages/Chapters';
import ChapterReader from './pages/ChapterReader';
import ChapterAnalysis from './pages/ChapterAnalysis';
import WritingStyles from './pages/WritingStyles';
import PatternAnalysis from './pages/PatternAnalysis';
import ProjectWiki from './pages/ProjectWiki'; // 导入 ProjectWiki
import { ConflictDetection } from './pages_new/ConflictDetection';
import { ChapterGraph } from './pages_new/ChapterGraph';
import Settings from './pages/Settings';
import MCPPlugins from './pages/MCPPlugins';
import UserManagement from './pages/UserManagement';
// import Polish from './pages/Polish';
import Login from './pages/Login';
import AuthCallback from './pages/AuthCallback';
import ProtectedRoute from './components/ProtectedRoute';
import './App.css';

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <BrowserRouter
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      >
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/auth/callback" element={<AuthCallback />} />

          <Route path="/" element={<ProtectedRoute><ProjectList /></ProtectedRoute>} />
          <Route path="/projects" element={<ProtectedRoute><ProjectList /></ProtectedRoute>} />
          <Route path="/wizard" element={<ProtectedRoute><ProjectWizardNew /></ProtectedRoute>} />
          <Route path="/inspiration" element={<ProtectedRoute><Inspiration /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
          <Route path="/mcp-plugins" element={<ProtectedRoute><MCPPlugins /></ProtectedRoute>} />
          <Route path="/user-management" element={<ProtectedRoute><UserManagement /></ProtectedRoute>} />
          <Route path="/chapters/:chapterId/reader" element={<ProtectedRoute><ChapterReader /></ProtectedRoute>} />
          <Route path="/project/:projectId" element={<ProtectedRoute><ProjectDetail /></ProtectedRoute>}>
            <Route index element={<Navigate to="world-setting" replace />} />
            <Route path="world-setting" element={<WorldSetting />} />
            <Route path="outline" element={<Outline />} />
            <Route path="characters" element={<Characters />} />
            <Route path="relationships" element={<Relationships />} />
            <Route path="organizations" element={<Organizations />} />
            <Route path="chapters" element={<Chapters />} />
            <Route path="chapter-analysis" element={<ChapterAnalysis />} />
            <Route path="conflict-detection" element={<ConflictDetection />} />
            <Route path="chapter-graph" element={<ChapterGraph />} />
            <Route path="writing-styles" element={<WritingStyles />} />
            <Route path="pattern-analysis" element={<PatternAnalysis />} />
            <Route path="wiki" element={<ProjectWiki />} /> {/* 新增项目百科路由 */}
            {/* <Route path="polish" element={<Polish />} /> */}
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
