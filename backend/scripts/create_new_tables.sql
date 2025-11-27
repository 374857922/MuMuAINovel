-- 新功能数据库表创建脚本
-- 用途：为设定追溯与矛盾检测、思维链图谱功能创建表

-- ========================================
-- 实体快照表（EntitySnapshot）
-- 用途：记录每个设定点的快照，用于追溯
-- ========================================
CREATE TABLE IF NOT EXISTS entity_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- 实体信息
    entity_type VARCHAR(30) NOT NULL,
    entity_id VARCHAR(36) NOT NULL,
    entity_name VARCHAR(200),

    -- 属性信息
    property_name VARCHAR(100) NOT NULL,
    property_value TEXT NOT NULL,
    property_type VARCHAR(30),

    -- 来源信息
    source_chapter_id VARCHAR(36) REFERENCES chapters(id) ON DELETE SET NULL,
    source_outline_id VARCHAR(36) REFERENCES outlines(id) ON DELETE SET NULL,
    source_quote TEXT,
    source_context TEXT,

    -- AI识别信息
    confidence FLOAT DEFAULT 0.8,
    ai_model VARCHAR(100),
    extraction_version VARCHAR(20),

    -- 元数据
    is_confirmed VARCHAR(1) DEFAULT 'N',
    tags TEXT,

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_entity_lookup ON entity_snapshots(project_id, entity_id, property_name);
CREATE INDEX IF NOT EXISTS idx_entity_type ON entity_snapshots(entity_type);
CREATE INDEX IF NOT EXISTS idx_confidence_filter ON entity_snapshots(confidence);

COMMENT ON TABLE entity_snapshots IS '实体快照表 - 记录每个设定点的快照';
COMMENT ON COLUMN entity_snapshots.entity_type IS '实体类型: character/location/item/rule';
COMMENT ON COLUMN entity_snapshots.property_name IS '属性名: age/location/ability/status';
COMMENT ON COLUMN entity_snapshots.property_type IS '属性类型: string/number/boolean/list';
COMMENT ON COLUMN entity_snapshots.confidence IS 'AI识别置信度（0-1）';
COMMENT ON COLUMN entity_snapshots.is_confirmed IS '是否人工确认: Y/N';

-- ========================================
-- 矛盾检测结果表（Conflict）
-- 用途：存储检测到的设定矛盾
-- ========================================
CREATE TABLE IF NOT EXISTS conflicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- 涉及实体
    entity_type VARCHAR(30) NOT NULL,
    entity_id VARCHAR(36) NOT NULL,
    entity_name VARCHAR(200),

    -- 矛盾的属性
    property_name VARCHAR(100) NOT NULL,
    property_display VARCHAR(200),

    -- 两个冲突的快照
    snapshot_a_id UUID NOT NULL REFERENCES entity_snapshots(id),
    snapshot_a_value TEXT,
    snapshot_a_source VARCHAR(36),

    snapshot_b_id UUID NOT NULL REFERENCES entity_snapshots(id),
    snapshot_b_value TEXT,
    snapshot_b_source VARCHAR(36),

    -- 矛盾信息
    conflict_type VARCHAR(30),
    severity VARCHAR(20) DEFAULT 'warning',
    description TEXT,

    -- 处理状态
    status VARCHAR(20) DEFAULT 'detected',
    resolution TEXT,
    resolved_by VARCHAR(36),
    resolved_at TIMESTAMP,

    -- AI信息
    confidence FLOAT,
    ai_suggestion TEXT,

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_entity_conflict ON conflicts(entity_id, property_name);
CREATE INDEX IF NOT EXISTS idx_project_status ON conflicts(project_id, status);
CREATE INDEX IF NOT EXISTS idx_severity_filter ON conflicts(severity);

COMMENT ON TABLE conflicts IS '矛盾检测结果表';
COMMENT ON COLUMN conflicts.conflict_type IS '矛盾类型: contradiction/inconsistency/ambiguity';
COMMENT ON COLUMN conflicts.severity IS '严重程度: critical/warning/info';
COMMENT ON COLUMN conflicts.status IS '状态: detected/verified/resolved/ignored';

-- ========================================
-- 章节关系链接表（ChapterLink）
-- 用途：存储章节之间的关系（因果、伏笔等）
-- ========================================
CREATE TABLE IF NOT EXISTS chapter_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- 关系两端
    from_chapter_id VARCHAR(36) NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    from_chapter_title VARCHAR(200),
    to_chapter_id VARCHAR(36) NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    to_chapter_title VARCHAR(200),

    -- 关系类型
    link_type VARCHAR(30) NOT NULL,
    link_type_display VARCHAR(50),

    -- 关系描述
    description TEXT,
    from_element TEXT,
    to_element TEXT,

    -- 推理链条（思维链）
    reasoning_chain TEXT,

    -- 强度与重要性
    strength FLOAT DEFAULT 0.5,
    importance_score FLOAT,

    -- AI信息
    confidence FLOAT,
    ai_model VARCHAR(100),

    -- 元数据
    is_confirmed VARCHAR(1) DEFAULT 'N',
    time_gap INTEGER,
    tags TEXT,

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 唯一约束
    UNIQUE (from_chapter_id, to_chapter_id, link_type)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_chapter_relation ON chapter_links(from_chapter_id, to_chapter_id);
CREATE INDEX IF NOT EXISTS idx_project_links ON chapter_links(project_id);
CREATE INDEX IF NOT EXISTS idx_link_type_filter ON chapter_links(link_type);
CREATE INDEX IF NOT EXISTS idx_importance_sort ON chapter_links(importance_score DESC);

COMMENT ON TABLE chapter_links IS '章节关系链接表';
COMMENT ON COLUMN chapter_links.link_type IS '关系类型: causality/foreshadowing/callback/parallel/contrast/continuation';
COMMENT ON COLUMN chapter_links.reasoning_chain IS '推理链条（JSON格式）';
COMMENT ON COLUMN chapter_links.is_confirmed IS '是否人工确认: Y/N';

-- ========================================
-- 思维链详细记录表（ThinkingChain）
-- 用途：存储AI推理过程
-- ========================================
CREATE TABLE IF NOT EXISTS thinking_chains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chapter_id VARCHAR(36) REFERENCES chapters(id) ON DELETE CASCADE,

    -- 思维链类型
    chain_type VARCHAR(30) NOT NULL,

    -- 思维过程
    reasoning_steps TEXT NOT NULL,
    conclusion TEXT,
    supporting_evidence TEXT,

    -- 关联的快照
    snapshot_ids TEXT,
    conflict_ids TEXT,
    link_ids TEXT,

    -- AI信息
    ai_model VARCHAR(100),
    temperature FLOAT,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_project_chains ON thinking_chains(project_id);
CREATE INDEX IF NOT EXISTS idx_chapter_chains ON thinking_chains(chapter_id);
CREATE INDEX IF NOT EXISTS idx_chain_type_filter ON thinking_chains(chain_type);

COMMENT ON TABLE thinking_chains IS '思维链详细记录表';
COMMENT ON COLUMN thinking_chains.chain_type IS '类型: generation/analysis/detection';
COMMENT ON COLUMN thinking_chains.reasoning_steps IS '推理步骤（JSON数组）';

-- ========================================
-- 示例查询（用于测试和验证）
-- ========================================

-- 查询某个项目的所有实体快照
-- SELECT * FROM entity_snapshots WHERE project_id = 'your_project_id' ORDER BY created_at;

-- 查询某个实体的所有矛盾
-- SELECT c.* FROM conflicts c WHERE entity_id = 'entity_id' ORDER BY created_at DESC;

-- 查询项目的章节关系（按重要性排序）
-- SELECT * FROM chapter_links WHERE project_id = 'your_project_id' ORDER BY importance_score DESC;

-- 查询某个章节的关系（包含入边和出边）
-- SELECT * FROM chapter_links WHERE project_id = 'your_project_id' AND (from_chapter_id = 'ch_id' OR to_chapter_id = 'ch_id');

-- ========================================
-- 注意事项
-- ========================================
-- 1. 所有外键都设置了ON DELETE CASCADE，删除项目时会自动清理关联数据
-- 2. UUID字段使用默认gen_random_uuid()自动生成
-- 3. 时间戳字段使用DEFAULT CURRENT_TIMESTAMP自动维护
-- 4. 索引已根据查询场景优化
