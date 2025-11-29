import React, { useMemo, forwardRef, useImperativeHandle, useRef } from 'react';
import CodeMirror from '@uiw/react-codemirror'; // 直接导入 CodeMirror 默认导出
import { EditorView, Decoration, ViewPlugin, ViewUpdate } from '@codemirror/view';
import { RangeSetBuilder } from '@codemirror/state';

// 自定义主题：让编辑器看起来更像写作软件
const writingTheme = EditorView.theme({
  '&': {
    fontSize: '16px',
    height: '100%',
    backgroundColor: '#fff',
  },
  // 强制开启滚动容器的样式
  '.cm-scroller': {
    overflow: 'auto',
    height: '100%',
  },
  '.cm-content': {
    fontFamily: "'PingFang SC', 'Microsoft YaHei', sans-serif",
    lineHeight: '1.8',
    padding: '16px 24px', // 左右边距调整为 24px
    maxWidth: '100%', // 移除 800px 限制，占满容器宽度
    margin: '0',      // 移除 auto margin
  },
  // ✨ 新增：中文首行缩进 2em
  '.cm-line': {
    padding: '0 4px',
    textIndent: '2em', 
  },
  '.cm-gutters': {
    backgroundColor: '#f5f5f5',
    color: '#ddd',
    border: 'none',
    display: 'none',
  },
  '&.cm-focused': {
    outline: 'none',
  },
  // 词条内容的高亮样式 (不包含括号)
  '.cm-wiki-content': {
    color: '#1890ff',
    backgroundColor: '#e6f7ff',
    borderRadius: '4px',
    padding: '0 4px',
    fontWeight: 'bold',
    borderBottom: '1px solid #91d5ff',
    textDecoration: 'none',
    display: 'inline-block',
    // 为了抵消父级的 text-indent，如果是行内元素不需要特殊处理，
    // 但如果有布局问题，可以加 text-indent: 0
    textIndent: '0', 
  },
});

// 定义装饰器类型
const hideBracketDeco = Decoration.replace({}); // 将括号替换为空(隐藏)
const contentDeco = Decoration.mark({ class: 'cm-wiki-content' }); // 词条内容样式

// 自定义插件：隐藏 [[ ]] 并高亮中间内容
const wikiLinkPlugin = ViewPlugin.fromClass(
  class {
    decorations: any;

    constructor(view: EditorView) {
      this.decorations = this.buildDecorations(view);
    }

    update(update: ViewUpdate) {
      if (update.docChanged || update.viewportChanged) {
        this.decorations = this.buildDecorations(update.view);
      }
    }

    buildDecorations(view: EditorView) {
      const builder = new RangeSetBuilder<Decoration>();
      
      for (const { from, to } of view.visibleRanges) {
        const text = view.state.doc.sliceString(from, to);
        const regex = /\[\[(.*?)\]\]/g;
        let match;

        while ((match = regex.exec(text))) {
          // 计算文档中的绝对位置
          const start = from + match.index;
          const end = start + match[0].length;
          const contentStart = start + 2; // 跳过 [[
          const contentEnd = end - 2;     // 跳过 ]]

          // 1. 隐藏 [[
          builder.add(start, contentStart, hideBracketDeco);
          
          // 2. 高亮中间内容
          builder.add(contentStart, contentEnd, contentDeco);
          
          // 3. 隐藏 ]]
          builder.add(contentEnd, end, hideBracketDeco);
        }
      }
      return builder.finish();
    }
  },
  {
    decorations: (v) => v.decorations,
    
    // ✨ 新增：原子范围属性
    // 这告诉编辑器：虽然 [[...]] 包含多个字符，但在光标移动和删除时，请把它当成一个整体。
    provide: (plugin) => EditorView.atomicRanges.of((view) => {
      const value = view.plugin(plugin);
      return value ? value.decorations : Decoration.none;
    })
  }
);

// 定义 CodeMirror ref 的实际类型
interface CodeMirrorInternalRef {
  editor?: HTMLDivElement;
  view?: EditorView;
}

export type SmartEditorRef = {
  scrollToBottom: () => void;
  getSelection: () => string;
  insertText: (text: string) => void;
  replaceSelection: (text: string) => void;
}

interface SmartEditorProps {
  value?: string; 
  onChange?: (value: string) => void;
  onSelectionChange?: (selection: string) => void; // 新增选区变化回调
  disabled?: boolean;
  height?: string;
  placeholder?: string;
}

export const SmartEditor = forwardRef<SmartEditorRef, SmartEditorProps>(({
  value = '',
  onChange,
  onSelectionChange,
  disabled = false,
  height = '500px',
  placeholder,
  style = {}, // <-- 为 style 提供一个默认的空对象
}, ref) => {
  const editorRef = useRef<CodeMirrorInternalRef>(null);

  useImperativeHandle(ref, () => ({
    scrollToBottom: () => {
      if (editorRef.current?.view) {
        const view = editorRef.current.view;
        const doc = view.state.doc;
        view.dispatch({
          effects: EditorView.scrollIntoView(doc.length, { y: 'end' })
        });
      }
    },
    getSelection: () => {
      if (editorRef.current?.view) {
        const state = editorRef.current.view.state;
        const selection = state.selection.main;
        return state.sliceDoc(selection.from, selection.to);
      }
      return '';
    },
    insertText: (text: string) => {
      if (editorRef.current?.view) {
        const view = editorRef.current.view;
        const transaction = view.state.update({
          changes: { from: view.state.selection.main.to, insert: text },
          scrollIntoView: true
        });
        view.dispatch(transaction);
      }
    },
    replaceSelection: (text: string) => {
      if (editorRef.current?.view) {
        const view = editorRef.current.view;
        const transaction = view.state.replaceSelection(text);
        view.dispatch(transaction);
      }
    }
  }));
  
  const extensions = useMemo(() => [
    writingTheme,
    wikiLinkPlugin,
    EditorView.lineWrapping, 
    // 监听选区变化
    EditorView.updateListener.of((update) => {
      if (update.selectionSet && onSelectionChange) {
        const selection = update.state.sliceDoc(
          update.state.selection.main.from,
          update.state.selection.main.to
        );
        onSelectionChange(selection);
      }
    }),
  ], [onSelectionChange]); // 依赖 onSelectionChange

    return (
      <div style={{
        border: '1px solid #d9d9d9',
        borderRadius: '6px',
        overflow: 'hidden',
        transition: 'border-color 0.2s',
        backgroundColor: disabled ? '#f5f5f5' : '#fff',
        outline: 'none',
        ...style, // 应用传入的样式
      }}
      className="smart-editor-container"
      >      <CodeMirror
        ref={editorRef}
        value={value}
        height={height}
        style={{ height: '100%' }} // 强制 CodeMirror 容器高度为 100%
        extensions={extensions}
        onChange={onChange}
        editable={!disabled}
        placeholder={placeholder}
        basicSetup={{
          lineNumbers: false,
          foldGutter: false,
          highlightActiveLine: false,
          highlightActiveLineGutter: false,
        }}
      />
    </div>
  );
});

SmartEditor.displayName = 'SmartEditor';
