import React, { useMemo, useEffect, useRef } from 'react';
import { Tooltip, Popover } from 'antd'; // 导入 Popover
import type { Term } from '../types/index'; // 显式使用 type 导入，并指定具体文件

// 标注数据类型
export interface MemoryAnnotation {
  id: string;
  type: 'hook' | 'foreshadow' | 'plot_point' | 'character_event';
  title: string;
  content: string;
  importance: number;
  position: number;
  length: number;
  tags: string[];
  metadata: {
    strength?: number;
    foreshadowType?: 'planted' | 'resolved';
    relatedCharacters?: string[];
    [key: string]: any;
  };
}

// 文本片段类型
interface TextSegment {
  type: 'text' | 'memory_annotated' | 'term_annotated'; // 更新类型
  content: string;
  memoryAnnotation?: MemoryAnnotation; // 单个记忆标注
  memoryAnnotations?: MemoryAnnotation[]; // 🔧 支持多个记忆标注
  term?: Term; // 词条标注
}

interface AnnotatedTextProps {
  content: string;
  annotations: MemoryAnnotation[];
  projectTerms: Term[]; // 新增：项目词条
  onAnnotationClick?: (annotation: MemoryAnnotation) => void;
  activeAnnotationId?: string;
  scrollToAnnotation?: string;
  style?: React.CSSProperties;
}

// 类型颜色映射
const TYPE_COLORS = {
  hook: '#ff6b6b',
  foreshadow: '#6b7bff',
  plot_point: '#51cf66',
  character_event: '#ffd93d',
};

// 类型图标映射
const TYPE_ICONS = {
  hook: '🎣',
  foreshadow: '🌟',
  plot_point: '💎',
  character_event: '👤',
};

/**
 * 带标注的文本组件
 * 将记忆标注可视化地展示在章节文本中
 */
const AnnotatedText: React.FC<AnnotatedTextProps> = ({
  content,
  annotations,
  projectTerms, // 解构 projectTerms
  onAnnotationClick,
  activeAnnotationId,
  scrollToAnnotation,
  style,
}) => {
  const annotationRefs = useRef<Record<string, HTMLSpanElement | null>>({});

  // 当需要滚动到特定标注时
  useEffect(() => {
    if (scrollToAnnotation && annotationRefs.current[scrollToAnnotation]) {
      const element = annotationRefs.current[scrollToAnnotation];
      element?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [scrollToAnnotation]);
  // 处理标注重叠和排序
  const processedAnnotations = useMemo(() => {
    if (!annotations || annotations.length === 0) {
      console.log('AnnotatedText: 没有标注数据');
      return [];
    }
    
    console.log(`AnnotatedText: 收到${annotations.length}个标注，内容长度${content.length}`);
    
    // 过滤掉无效位置的标注
    const validAnnotations = annotations.filter(
      (a) => a.position >= 0 && a.position < content.length
    );
    
    const invalidCount = annotations.length - validAnnotations.length;
    if (invalidCount > 0) {
      console.warn(`AnnotatedText: ${invalidCount}个标注位置无效，有效标注${validAnnotations.length}个`);
      console.log('无效标注:', annotations.filter(a => a.position < 0 || a.position >= content.length));
    }
    
    // 按位置排序
    return validAnnotations.sort((a, b) => a.position - b.position);
  }, [annotations, content, projectTerms]); // 增加 projectTerms 依赖

  // 将文本分割为带标注的片段
  const segments = useMemo(() => {
    if (!content) return [];

    const combinedAnnotations: Array<{
      start: number;
      end: number;
      type: 'memory' | 'term';
      data: MemoryAnnotation | Term;
    }> = [];

    // 1. 处理 Memory Annotations
    if (processedAnnotations.length > 0) {
      for (const annotation of processedAnnotations) {
        const { position, length } = annotation;
        const actualLength = length > 0 ? length : annotation.content.length; // 如果长度为0，用内容长度代替
        if (position >= 0 && position < content.length && actualLength > 0) {
          combinedAnnotations.push({
            start: position,
            end: position + actualLength,
            type: 'memory',
            data: annotation,
          });
        } else {
          console.warn("Invalid memory annotation position or length:", annotation);
        }
      }
    }

    // 2. 处理 Term Annotations (Markdown [[term]])
    const TERM_REGEX = /\[\[([^\]]+)\]\]/g;
    let match;
    while ((match = TERM_REGEX.exec(content)) !== null) {
      const fullMatch = match[0]; // [[词条名称]]
      const termName = match[1]; // 词条名称
      const start = match.index;
      const end = match.index + fullMatch.length;
      
      const foundTerm = projectTerms.find(term => term.name === termName);
      if (foundTerm) {
        // 检查是否与现有记忆标注重叠，如果完全重叠则忽略词条标注
        const isOverlappedByMemory = combinedAnnotations.some(anno => 
          anno.type === 'memory' &&
          ((start >= anno.start && start < anno.end) ||
           (end > anno.start && end <= anno.end) ||
           (start <= anno.start && end >= anno.end))
        );

        if (!isOverlappedByMemory) {
          combinedAnnotations.push({
            start,
            end,
            type: 'term',
            data: foundTerm,
          });
        }
      }
    }

    // 3. 排序所有标注（按开始位置）
    combinedAnnotations.sort((a, b) => a.start - b.start);

    const result: TextSegment[] = [];
    let lastPos = 0;

    for (const anno of combinedAnnotations) {
      // 添加前面的普通文本
      if (anno.start > lastPos) {
        result.push({
          type: 'text',
          content: content.slice(lastPos, anno.start),
        });
      }

      // 添加标注文本
      if (anno.type === 'memory') {
        result.push({
          type: 'memory_annotated',
          content: content.slice(anno.start, anno.end),
          memoryAnnotation: anno.data as MemoryAnnotation,
          memoryAnnotations: [anno.data as MemoryAnnotation], // 简化处理，暂时只传单个
        });
      } else if (anno.type === 'term') {
        result.push({
          type: 'term_annotated',
          content: content.slice(anno.start, anno.end),
          term: anno.data as Term,
        });
      }

      lastPos = Math.max(lastPos, anno.end);
    }

    // 添加剩余文本
    if (lastPos < content.length) {
      result.push({
        type: 'text',
        content: content.slice(lastPos),
      });
    }

    console.log(`AnnotatedText: 处理了 ${processedAnnotations.length} 个记忆标注和 ${projectTerms.length} 个词条，生成了 ${result.length} 个片段`);
    return result;
  }, [content, processedAnnotations, projectTerms]);

  // 渲染标注片段
  const renderAnnotatedSegment = (segment: TextSegment, index: number) => {
    if (segment.type === 'text') {
      return <span key={index}>{segment.content}</span>;
    } else if (segment.type === 'term_annotated') {
      const { term } = segment;
      if (!term) return null;

      const termContent = term.name; // 显示词条名称，而不是 [[词条名称]]

      const popoverContent = (
        <div style={{ maxWidth: 300 }}>
          <div style={{ fontWeight: 'bold', marginBottom: 4 }}>
            📖 {term.name}
          </div>
          <div style={{ fontSize: 12, opacity: 0.9 }}>
            {term.description || '暂无描述'}
          </div>
          <div style={{ marginTop: 8, fontSize: 11, opacity: 0.7 }}>
            创建于: {new Date(term.created_at).toLocaleDateString()}
          </div>
        </div>
      );

      return (
        <Popover key={index} content={popoverContent} title={null} placement="top">
          <span
            className="term-highlight"
            style={{
              position: 'relative',
              borderBottom: '2px dashed #4096ff',
              cursor: 'help',
              transition: 'background-color 0.2s',
              padding: '2px 0',
              color: '#0050b3' // 词条使用蓝色字体
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#e6f4ff';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
            }}
          >
            {termContent}
          </span>
        </Popover>
      );
    }

    // Original memory annotation rendering logic
    const { memoryAnnotation, memoryAnnotations } = segment;
    if (!memoryAnnotation) return null;

    const color = TYPE_COLORS[memoryAnnotation.type];
    const icon = TYPE_ICONS[memoryAnnotation.type];
    const isActive = activeAnnotationId === memoryAnnotation.id;

    // 🔧 工具提示内容：如果有多个标注，显示所有标注信息
    const tooltipContent = (
      <div style={{ maxWidth: 350 }}>
        {memoryAnnotations && memoryAnnotations.length > 1 ? (
          // 多个标注
          <div>
            <div style={{ fontWeight: 'bold', marginBottom: 8, borderBottom: '1px solid rgba(255,255,255,0.3)', paddingBottom: 4 }}>
              📍 此处有 {memoryAnnotations.length} 个标注
            </div>
            {memoryAnnotations.map((ann, idx) => (
              <div key={ann.id} style={{
                marginBottom: idx < memoryAnnotations.length - 1 ? 8 : 0,
                paddingBottom: idx < memoryAnnotations.length - 1 ? 8 : 0,
                borderBottom: idx < memoryAnnotations.length - 1 ? '1px solid rgba(255,255,255,0.1)' : 'none'
              }}>
                <div style={{ fontWeight: 'bold', marginBottom: 4, fontSize: 13 }}>
                  {TYPE_ICONS[ann.type]} {ann.title}
                </div>
                <div style={{ fontSize: 11, opacity: 0.9 }}>
                  {ann.content.slice(0, 80)}
                  {ann.content.length > 80 ? '...' : ''}
                </div>
                <div style={{ marginTop: 4, fontSize: 10, opacity: 0.7 }}>
                  重要性: {(ann.importance * 10).toFixed(1)}/10
                </div>
              </div>
            ))}
          </div>
        ) : (
          // 单个标注
          <div>
            <div style={{ fontWeight: 'bold', marginBottom: 4 }}>
              {icon} {memoryAnnotation.title}
            </div>
            <div style={{ fontSize: 12, opacity: 0.9 }}>
              {memoryAnnotation.content.slice(0, 100)}
              {memoryAnnotation.content.length > 100 ? '...' : ''}
            </div>
            <div style={{ marginTop: 8, fontSize: 11, opacity: 0.7 }}>
              重要性: {(memoryAnnotation.importance * 10).toFixed(1)}/10
            </div>
            {memoryAnnotation.tags && memoryAnnotation.tags.length > 0 && (
              <div style={{ marginTop: 4, fontSize: 11 }}>
                {memoryAnnotation.tags.map((tag, i) => (
                  <span
                    key={i}
                    style={{
                      display: 'inline-block',
                      background: 'rgba(255,255,255,0.2)',
                      padding: '2px 6px',
                      borderRadius: 3,
                      marginRight: 4,
                    }}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    );

    return (
      <Tooltip key={index} title={tooltipContent} placement="top">
        <span
          ref={(el) => {
            if (memoryAnnotation) {
              annotationRefs.current[memoryAnnotation.id] = el;
            }
          }}
          data-annotation-id={memoryAnnotation?.id}
          className={`annotated-text ${isActive ? 'active' : ''}`}
          style={{
            position: 'relative',
            borderBottom: `2px solid ${color}`,
            cursor: 'pointer',
            backgroundColor: isActive ? `${color}22` : 'transparent',
            transition: 'all 0.2s',
            padding: '2px 0',
          }}
          onClick={() => onAnnotationClick?.(memoryAnnotation)}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = `${color}33`;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = isActive
              ? `${color}22`
              : 'transparent';
          }}
        >
          {segment.content}
          <span
            style={{
              position: 'absolute',
              top: -20,
              left: '50%',
              transform: 'translateX(-50%)',
              fontSize: 14,
              pointerEvents: 'none',
            }}
          >
            {icon}
          </span>
        </span>
      </Tooltip>
    );
  };

  return (
    <div
      style={{
        lineHeight: 2,
        fontSize: 16,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        ...style,
      }}
    >
      {segments.map((segment, index) => renderAnnotatedSegment(segment, index))}
    </div>
  );
};

export default AnnotatedText;