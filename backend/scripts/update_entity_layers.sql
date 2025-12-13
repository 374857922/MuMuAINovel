-- 更新 entity_snapshots 表，支持多维属性分层检测

-- 1. 添加 layer 字段 (属性层级)
-- 用于区分: Intrinsic (真相/固有), Appearance (表象/伪装), Evaluation (评价/主观)
ALTER TABLE entity_snapshots ADD COLUMN IF NOT EXISTS layer VARCHAR(50) DEFAULT 'Intrinsic';

-- 2. 添加 source_type 字段 (来源类型)
-- 用于区分: Narrator (旁白), Character (角色口述)
ALTER TABLE entity_snapshots ADD COLUMN IF NOT EXISTS source_type VARCHAR(50) DEFAULT 'Narrator';

-- 3. 添加注释 (PostgreSQL 特有语法，如果是 SQLite 可忽略)
COMMENT ON COLUMN entity_snapshots.layer IS '属性层级: Intrinsic(固有)/Appearance(表象)/Evaluation(评价)';
COMMENT ON COLUMN entity_snapshots.source_type IS '来源类型: Narrator(旁白)/Character(角色)';
