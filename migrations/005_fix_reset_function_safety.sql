-- Fix for 'UPDATE requires a WHERE clause' error in reset_weekly_scores
CREATE OR REPLACE FUNCTION reset_weekly_scores()
RETURNS void AS $$
BEGIN
    -- Added WHERE clause to satisfy safe update policy
    UPDATE users SET weekly_score = 0.0 WHERE weekly_score != 0;
END;
$$ LANGUAGE plpgsql;
