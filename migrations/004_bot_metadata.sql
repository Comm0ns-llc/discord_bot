-- ============================================
-- Table: bot_metadata
-- Botの内部状態や設定値を保存
-- ============================================
CREATE TABLE IF NOT EXISTS bot_metadata (
    key VARCHAR(255) PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE bot_metadata IS 'Botの内部状態管理テーブル';
