-- Analytics Views Migration
-- Run this in Supabase SQL Editor

-- 1. Daily Pulse (Time Series of Activity & Quality)
CREATE OR REPLACE VIEW analytics_daily_pulse AS
SELECT
  DATE_TRUNC('day', timestamp) AS day,
  COUNT(*) AS total_messages,
  COUNT(DISTINCT user_id) AS active_users,
  SUM(total_score) AS total_score,
  AVG(nlp_score_multiplier) AS avg_quality,
  SUM(reaction_score) AS total_reaction_score
FROM messages
GROUP BY 1
ORDER BY 1 DESC;

-- 2. Social Graph (Who reacts to whom)
-- Source: Reactor (r.user_id) -> Target: Author (m.user_id)
CREATE OR REPLACE VIEW analytics_social_graph AS
SELECT
  r.user_id AS source_user,
  m.user_id AS target_user,
  COUNT(*) AS weight,
  MAX(r.created_at) AS last_interaction
FROM reactions r
JOIN messages m ON r.message_id = m.message_id
WHERE r.user_id != m.user_id
GROUP BY 1, 2;

-- 3. Hourly Heatmap (When is the server active?)
CREATE OR REPLACE VIEW analytics_hourly_heatmap AS
SELECT
  EXTRACT(DOW FROM timestamp) AS day_of_week, -- 0=Sunday, 6=Saturday
  EXTRACT(HOUR FROM timestamp) AS hour_of_day, -- 0-23
  COUNT(*) AS message_count,
  SUM(total_score) AS total_intensity
FROM messages
GROUP BY 1, 2
ORDER BY 1, 2;

-- 4. User Leaderboard View (Enriched)
CREATE OR REPLACE VIEW analytics_leaderboard AS
SELECT 
    u.user_id, 
    u.username, 
    u.current_score, 
    u.weekly_score,
    (SELECT COUNT(*) FROM messages m WHERE m.user_id = u.user_id) as total_messages,
    u.updated_at
FROM users u
ORDER BY u.current_score DESC;

-- 5. Channel Ranking (Most active channels)
-- 5. Channel Ranking (Most active channels)
DROP VIEW IF EXISTS analytics_channel_ranking CASCADE;

CREATE OR REPLACE VIEW analytics_channel_ranking AS
SELECT
    m.channel_id,
    COALESCE(c.name, CAST(m.channel_id AS VARCHAR)) AS channel_name,
    COUNT(m.message_id) AS total_messages,
    COUNT(DISTINCT m.user_id) AS active_users,
    SUM(m.total_score) AS total_score,
    AVG(m.nlp_score_multiplier) AS avg_quality,
    MAX(m.timestamp) AS last_active
FROM messages m
LEFT JOIN channels c ON m.channel_id = c.channel_id
GROUP BY 1, 2
ORDER BY total_messages DESC;

-- 6. Channel Top User (Who speaks most in each channel)
DROP VIEW IF EXISTS analytics_channel_leader_user CASCADE;

CREATE OR REPLACE VIEW analytics_channel_leader_user AS
WITH ChannelUserCounts AS (
    SELECT
        channel_id,
        user_id,
        COUNT(*) as message_count
    FROM messages
    GROUP BY channel_id, user_id
),
RankedChannelUsers AS (
    SELECT
        channel_id,
        user_id,
        message_count,
        ROW_NUMBER() OVER (PARTITION BY channel_id ORDER BY message_count DESC) as rn
    FROM ChannelUserCounts
)
SELECT
    rc.channel_id,
    COALESCE(c.name, CAST(rc.channel_id AS VARCHAR)) AS channel_name,
    rc.user_id,
    u.username,
    rc.message_count
FROM RankedChannelUsers rc
JOIN users u ON rc.user_id = u.user_id
LEFT JOIN channels c ON rc.channel_id = c.channel_id
WHERE rc.rn = 1
ORDER BY rc.message_count DESC;
