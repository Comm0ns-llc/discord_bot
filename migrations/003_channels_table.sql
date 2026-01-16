-- Channels Table Migration
-- Run this in Supabase SQL Editor

-- ============================================
-- Table: channels
-- チャンネル情報を管理
-- ============================================
CREATE TABLE IF NOT EXISTS channels (
    channel_id BIGINT PRIMARY KEY,                 -- Discord Channel ID
    name VARCHAR(255) NOT NULL,                    -- Channel Name
    type VARCHAR(50),                              -- Channel Type (text, voice, etc.)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- Function: Update updated_at timestamp
-- ============================================
-- Note: update_updated_at_column function already exists from 001_initial_schema.sql

-- ============================================
-- Triggers
-- ============================================
DROP TRIGGER IF EXISTS update_channels_updated_at ON channels;
CREATE TRIGGER update_channels_updated_at
    BEFORE UPDATE ON channels
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Indexes
-- ============================================
CREATE INDEX IF NOT EXISTS idx_channels_name ON channels(name);
