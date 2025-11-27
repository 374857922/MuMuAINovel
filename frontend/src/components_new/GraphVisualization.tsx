import React, { useEffect, useRef, useState } from 'react';
import * as echarts from 'echarts';
import { Radio, Slider, Switch, Space, Typography, Tooltip } from 'antd';
import { ZoomInOutlined, ZoomOutOutlined, AimOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface GraphData {
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
}

interface GraphVisualizationProps {
  graphData: GraphData;
  loading: boolean;
  selectedLinkType: string;
  onNodeClick: (node: any) => void;
}

// 关系类型配置
const LINK_CONFIG: Record<string, { color: string; name: string; dash?: number[] }> = {
  causality: { color: '#52c41a', name: '因果关系' },
  foreshadowing: { color: '#faad14', name: '伏笔埋设', dash: [5, 5] },
  callback: { color: '#1890ff', name: '伏笔回收' },
  parallel: { color: '#722ed1', name: '平行叙事', dash: [10, 5] },
  contrast: { color: '#ff4d4f', name: '对比冲突' },
  continuation: { color: '#13c2c2', name: '承上启下' }
};

// 节点重要性颜色梯度
const getNodeColor = (importance: number): string => {
  if (importance >= 80) return '#ff4d4f';  // 关键章节 - 红色
  if (importance >= 60) return '#faad14';  // 重要章节 - 金色
  if (importance >= 40) return '#1890ff';  // 普通章节 - 蓝色
  return '#8c8c8c';  // 次要章节 - 灰色
};

export const GraphVisualization: React.FC<GraphVisualizationProps> = ({
  graphData,
  loading,
  selectedLinkType,
  onNodeClick
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const [viewMode, setViewMode] = useState<'force' | 'timeline'>('force');
  const [showLabels, setShowLabels] = useState(true);
  const [linkWidth, setLinkWidth] = useState(2);
  const [highlightedPath, setHighlightedPath] = useState<string[]>([]);

  // 筛选链接
  const filteredLinks = selectedLinkType === 'all'
    ? graphData.links
    : graphData.links.filter(link => link.type === selectedLinkType);

  // 获取有效节点（只显示有连接的节点）
  const connectedNodeIds = new Set<string>();
  filteredLinks.forEach(link => {
    connectedNodeIds.add(link.source);
    connectedNodeIds.add(link.target);
  });
  
  const filteredNodes = graphData.nodes.filter(node => 
    connectedNodeIds.has(node.id) || filteredLinks.length === 0
  );

  useEffect(() => {
    if (!chartRef.current) return;

    // 初始化图表
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, undefined, {
        renderer: 'canvas'
      });
    }

    const chart = chartInstance.current;

    // 构建节点数据
    const nodes = filteredNodes.map((node, index) => {
      const isHighlighted = highlightedPath.includes(node.id);
      
      // 时间线布局位置
      const timelineX = viewMode === 'timeline' 
        ? 100 + (node.chapterNumber - 1) * 120 
        : undefined;
      const timelineY = viewMode === 'timeline' 
        ? 300 + (index % 3 - 1) * 80 
        : undefined;

      return {
        id: node.id,
        name: `第${node.chapterNumber}章`,
        ...node,
        x: timelineX,
        y: timelineY,
        fixed: viewMode === 'timeline',
        symbolSize: Math.max(25, node.size + (isHighlighted ? 10 : 0)),
        label: {
          show: showLabels,
          formatter: viewMode === 'timeline' ? `{b}\n${node.title.slice(0, 6)}` : '{b}',
          fontSize: 11,
          color: '#333',
          distance: 5
        },
        itemStyle: {
          color: getNodeColor(node.importance),
          borderColor: isHighlighted ? '#000' : '#fff',
          borderWidth: isHighlighted ? 3 : 2,
          shadowBlur: isHighlighted ? 15 : 5,
          shadowColor: isHighlighted ? 'rgba(0,0,0,0.5)' : 'rgba(0,0,0,0.2)'
        }
      };
    });

    // 构建边数据
    const edges = filteredLinks.map(link => {
      const config = LINK_CONFIG[link.type] || LINK_CONFIG.continuation;
      const isHighlighted = highlightedPath.includes(link.source) && 
                           highlightedPath.includes(link.target);
      
      return {
        ...link,
        lineStyle: {
          color: config.color,
          width: (link.strength * linkWidth * 2) + (isHighlighted ? 2 : 0),
          type: config.dash ? 'dashed' : 'solid',
          curveness: viewMode === 'timeline' ? 0.3 : 0.2,
          opacity: isHighlighted ? 1 : 0.7
        },
        emphasis: {
          lineStyle: {
            width: link.strength * linkWidth * 3,
            opacity: 1
          }
        }
      };
    });

    // 配置选项
    const option: echarts.EChartsOption = {
      backgroundColor: '#fafafa',
      title: {
        text: viewMode === 'timeline' ? '章节时间线' : '章节关系网络',
        subtext: `${filteredNodes.length} 个章节，${filteredLinks.length} 个关系`,
        left: 'center',
        top: 10,
        textStyle: { fontSize: 16, fontWeight: 'bold' }
      },
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(255,255,255,0.95)',
        borderColor: '#ddd',
        borderWidth: 1,
        padding: 12,
        textStyle: { color: '#333' },
        formatter: (params: any) => {
          if (params.dataType === 'node') {
            const importance = params.data.importance || 0;
            const level = importance >= 80 ? '关键' : importance >= 60 ? '重要' : importance >= 40 ? '普通' : '次要';
            return `
              <div style="font-weight:bold;margin-bottom:8px;">第 ${params.data.chapterNumber} 章</div>
              <div style="color:#666;margin-bottom:4px;">${params.data.title}</div>
              <div style="margin-top:8px;">
                <span style="color:${getNodeColor(importance)};">●</span> 
                重要性: ${importance}/100 (${level})
              </div>
            `;
          } else if (params.dataType === 'edge') {
            const config = LINK_CONFIG[params.data.type] || {};
            return `
              <div style="font-weight:bold;margin-bottom:8px;">
                <span style="color:${config.color};">■</span> 
                ${config.name || params.data.type}
              </div>
              <div style="color:#666;max-width:250px;word-wrap:break-word;">
                ${params.data.description || '暂无描述'}
              </div>
              <div style="margin-top:8px;color:#999;">
                强度: ${(params.data.strength * 100).toFixed(0)}%
              </div>
            `;
          }
        }
      },
      legend: {
        show: true,
        data: Object.entries(LINK_CONFIG).map(([key, value]) => ({
          name: value.name,
          icon: 'roundRect'
        })),
        orient: 'vertical',
        left: 10,
        top: 60,
        textStyle: { fontSize: 12 },
        selectedMode: 'multiple',
        itemWidth: 16,
        itemHeight: 10
      },
      toolbox: {
        show: true,
        right: 20,
        top: 60,
        feature: {
          saveAsImage: { title: '保存图片' },
          restore: { title: '重置' }
        }
      },
      series: [{
        type: 'graph',
        layout: viewMode === 'timeline' ? 'none' : 'force',
        data: nodes,
        links: edges,
        categories: Object.entries(LINK_CONFIG).map(([key, value]) => ({
          name: value.name
        })),
        roam: true,
        zoom: 1,
        focusNodeAdjacency: true,
        draggable: viewMode !== 'timeline',
        force: viewMode === 'force' ? {
          repulsion: 800,
          gravity: 0.08,
          edgeLength: [100, 200],
          layoutAnimation: true,
          friction: 0.6
        } : undefined,
        emphasis: {
          focus: 'adjacency',
          blurScope: 'global',
          itemStyle: {
            borderWidth: 4,
            shadowBlur: 20,
            shadowColor: 'rgba(0,0,0,0.4)'
          },
          lineStyle: {
            width: 4
          }
        },
        select: {
          itemStyle: {
            borderColor: '#000',
            borderWidth: 3
          }
        }
      }],
      // 时间线模式下添加x轴
      ...(viewMode === 'timeline' ? {
        xAxis: {
          type: 'value',
          show: false
        },
        yAxis: {
          type: 'value', 
          show: false
        }
      } : {})
    };

    chart.setOption(option, true);

    // 绑定事件
    chart.off('click');
    chart.on('click', (params: any) => {
      if (params.dataType === 'node') {
        onNodeClick(params.data);
      }
    });

    // 双击高亮路径
    chart.off('dblclick');
    chart.on('dblclick', (params: any) => {
      if (params.dataType === 'node') {
        const nodeId = params.data.id;
        // 找到与该节点相连的所有节点
        const connectedNodes = new Set<string>([nodeId]);
        filteredLinks.forEach(link => {
          if (link.source === nodeId) connectedNodes.add(link.target);
          if (link.target === nodeId) connectedNodes.add(link.source);
        });
        setHighlightedPath(Array.from(connectedNodes));
      }
    });

    // 窗口大小变化时重新调整
    const handleResize = () => chart.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.off('click');
      chart.off('dblclick');
    };
  }, [graphData, selectedLinkType, viewMode, showLabels, linkWidth, highlightedPath, filteredLinks, filteredNodes, onNodeClick]);

  // 组件卸载时销毁
  useEffect(() => {
    return () => {
      if (chartInstance.current) {
        chartInstance.current.dispose();
        chartInstance.current = null;
      }
    };
  }, []);

  // 缩放控制
  const handleZoom = (direction: 'in' | 'out') => {
    if (chartInstance.current) {
      const currentZoom = (chartInstance.current.getOption() as any).series?.[0]?.zoom || 1;
      const newZoom = direction === 'in' ? currentZoom * 1.2 : currentZoom / 1.2;
      chartInstance.current.setOption({
        series: [{ zoom: Math.max(0.3, Math.min(3, newZoom)) }]
      });
    }
  };

  // 重置视图
  const handleReset = () => {
    setHighlightedPath([]);
    if (chartInstance.current) {
      chartInstance.current.setOption({
        series: [{ zoom: 1, center: undefined }]
      });
    }
  };

  return (
    <div style={{ position: 'relative' }}>
      {/* 控制面板 */}
      <div style={{ 
        marginBottom: 12, 
        padding: '8px 12px',
        background: '#fff',
        borderRadius: 6,
        border: '1px solid #e8e8e8',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12
      }}>
        <Space size="middle">
          <span>
            <Text type="secondary">视图模式：</Text>
            <Radio.Group 
              value={viewMode} 
              onChange={e => setViewMode(e.target.value)}
              size="small"
              optionType="button"
              buttonStyle="solid"
            >
              <Radio.Button value="force">力导向</Radio.Button>
              <Radio.Button value="timeline">时间线</Radio.Button>
            </Radio.Group>
          </span>
          
          <span>
            <Text type="secondary">显示标签：</Text>
            <Switch 
              checked={showLabels} 
              onChange={setShowLabels}
              size="small"
            />
          </span>
          
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Text type="secondary">连线粗细：</Text>
            <Slider
              value={linkWidth}
              onChange={setLinkWidth}
              min={1}
              max={5}
              style={{ width: 80 }}
            />
          </span>
        </Space>

        <Space>
          <Tooltip title="放大">
            <ZoomInOutlined 
              style={{ fontSize: 18, cursor: 'pointer', color: '#1890ff' }}
              onClick={() => handleZoom('in')}
            />
          </Tooltip>
          <Tooltip title="缩小">
            <ZoomOutOutlined 
              style={{ fontSize: 18, cursor: 'pointer', color: '#1890ff' }}
              onClick={() => handleZoom('out')}
            />
          </Tooltip>
          <Tooltip title="重置视图">
            <AimOutlined 
              style={{ fontSize: 18, cursor: 'pointer', color: '#1890ff' }}
              onClick={handleReset}
            />
          </Tooltip>
        </Space>
      </div>

      {/* 图例说明 */}
      <div style={{
        marginBottom: 8,
        padding: '6px 12px',
        background: 'linear-gradient(135deg, #f5f7fa 0%, #e4e8eb 100%)',
        borderRadius: 6,
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        flexWrap: 'wrap',
        fontSize: 12
      }}>
        <Text type="secondary">节点颜色：</Text>
        <span><span style={{ color: '#ff4d4f' }}>●</span> 关键章节</span>
        <span><span style={{ color: '#faad14' }}>●</span> 重要章节</span>
        <span><span style={{ color: '#1890ff' }}>●</span> 普通章节</span>
        <span><span style={{ color: '#8c8c8c' }}>●</span> 次要章节</span>
        <Text type="secondary" style={{ marginLeft: 'auto' }}>
          提示：双击节点高亮相关路径
        </Text>
      </div>

      {/* 图表容器 */}
      <div
        ref={chartRef}
        style={{
          width: '100%',
          height: '550px',
          backgroundColor: '#fafafa',
          border: '1px solid #d9d9d9',
          borderRadius: '6px',
          boxShadow: 'inset 0 2px 8px rgba(0,0,0,0.05)'
        }}
      />

      {/* 加载遮罩 */}
      {loading && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(255,255,255,0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 6
        }}>
          <Text type="secondary">加载中...</Text>
        </div>
      )}
    </div>
  );
};
