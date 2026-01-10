-- Discord Bot Database Schema
-- Run this migration in Supabase SQL Editor

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- Table: users
-- ユーザー情報とスコアを管理
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,                    -- Discord User ID
    username VARCHAR(255) NOT NULL,                -- Discord Username
    current_score DECIMAL(10, 2) DEFAULT 0.0,      -- 累計スコア
    weekly_score DECIMAL(10, 2) DEFAULT 0.0,       -- 週間スコア
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- Table: messages
-- メッセージ情報とNLP分析結果を保存
-- ============================================
CREATE TABLE IF NOT EXISTS messages (
    message_id BIGINT PRIMARY KEY,                 -- Discord Message ID
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    channel_id BIGINT NOT NULL,                    -- Discord Channel ID
    guild_id BIGINT NOT NULL,                      -- Discord Guild/Server ID
    content TEXT,                                  -- メッセージ内容（プライバシー考慮で暗号化推奨）
    nlp_score_multiplier DECIMAL(3, 2) DEFAULT 1.0, -- NLP分析による係数 (0.1 ~ 1.5)
    base_score DECIMAL(10, 2) DEFAULT 1.0,         -- 基本スコア
    reply_count INTEGER DEFAULT 0,                 -- このメッセージへのリプライ数
    reaction_score DECIMAL(10, 2) DEFAULT 0.0,     -- リアクションによるスコア
    total_score DECIMAL(10, 2) DEFAULT 0.0,        -- メッセージの合計スコア
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- Table: reactions
-- リアクション情報を管理
-- ============================================
CREATE TABLE IF NOT EXISTS reactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id BIGINT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,                       -- リアクションしたユーザーのID
    reaction_type VARCHAR(100) NOT NULL,           -- 絵文字の名前またはUnicode
    weight DECIMAL(3, 2) DEFAULT 2.0,              -- リアクションの重み
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 同じユーザーが同じメッセージに同じリアクションを複数回記録しない
    UNIQUE(message_id, user_id, reaction_type)
);

-- ============================================
-- Indexes for performance
-- ============================================
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_guild_id ON messages(guild_id);
CREATE INDEX IF NOT EXISTS idx_reactions_message_id ON reactions(message_id);
CREATE INDEX IF NOT EXISTS idx_users_current_score ON users(current_score DESC);
CREATE INDEX IF NOT EXISTS idx_users_weekly_score ON users(weekly_score DESC);

-- ============================================
-- Function: Update updated_at timestamp
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- ============================================
-- Triggers
-- ============================================
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Function: Reset weekly scores (run weekly via cron)
-- ============================================
CREATE OR REPLACE FUNCTION reset_weekly_scores()
RETURNS void AS $$
BEGIN
    UPDATE users SET weekly_score = 0.0;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- RLS (Row Level Security) - Optional but recommended
-- ============================================
-- ALTER TABLE users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE reactions ENABLE ROW LEVEL SECURITY;

-- ============================================
-- Comments
-- ============================================
COMMENT ON TABLE users IS 'Discordユーザーのスコア情報を管理';
COMMENT ON TABLE messages IS 'メッセージとNLP分析結果を保存';
COMMENT ON TABLE reactions IS 'メッセージへのリアクション情報';
COMMENT ON COLUMN messages.nlp_score_multiplier IS 'NLP分析による品質係数 (0.1=スパム, 1.0=通常, 1.5=高品質)';
