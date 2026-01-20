
import asyncio
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    print("Error: SUPABASE_URL or SUPABASE_KEY not set")
    exit(1)

client = create_client(url, key)

# Target User
TARGET_USERNAME = "Tsukuru86"

# Start of Week (Monday 00:00 JST = Sunday 15:00 UTC)
# Today is Wed Jan 21 (JST). Start of week is Mon Jan 19 00:00 JST.
# Jan 19 00:00 JST = Jan 18 15:00 UTC.
START_TIME_UTC = "2026-01-18T15:00:00+00:00"

async def verify_score():
    print(f"--- Verifying Weekly Score for {TARGET_USERNAME} ---")
    print(f"Counting events since: {START_TIME_UTC} (UTC)")

    # 1. Get User ID
    user_resp = client.table("users").select("user_id, weekly_score").eq("username", TARGET_USERNAME).execute()
    if not user_resp.data:
        print(f"User {TARGET_USERNAME} not found.")
        return
    
    user = user_resp.data[0]
    user_id = user["user_id"]
    current_weekly_score = float(user["weekly_score"])
    print(f"Current DB Weekly Score: {current_weekly_score}")

    # 2. Calculate Message Score (Sent this week)
    # Score = base_score * nlp_score_multiplier
    msgs_resp = client.table("messages").select("base_score, nlp_score_multiplier, created_at").eq("user_id", user_id).gte("created_at", START_TIME_UTC).execute()
    
    calc_msg_score = 0.0
    msg_count = 0
    if msgs_resp.data:
        for m in msgs_resp.data:
            score = float(m["base_score"]) * float(m["nlp_score_multiplier"])
            calc_msg_score += score
            msg_count += 1
            
    print(f"\n[Messages]")
    print(f"Count: {msg_count}")
    print(f"Calculated Score: {calc_msg_score:.2f}")

    # 3. Calculate Reaction Score (Received this week)
    # Reaction on ANY of user's messages, but reaction created_at must be this week.
    
    # First, get ALL message IDs by user (to check if reaction is on their message)
    # This might be large, but let's try.
    # Actually, Supabase filtering on foreign key? 
    # Can we do `reactions.select(*).eq(message.user_id, user_id)`? No.
    # We have to fetch user's message IDs first.
    
    # But wait, checking specific user's received reactions requires joining messages.
    # Let's fetch reactions created this week first (likely smaller set than all messages ever), 
    # then filter by message ownership?
    # Or fetch all messages by user (could be thousands) -> list of IDs -> fetch reactions where message_id in list AND created_at > start.
    
    # Let's try fetching user's messages first (just IDs).
    user_msgs_resp = client.table("messages").select("message_id").eq("user_id", user_id).execute()
    user_msg_ids = [m["message_id"] for m in user_msgs_resp.data]
    
    calc_reaction_score = 0.0
    reaction_count = 0
    
    if user_msg_ids:
        # Split into chunks if too many, but for now try all
        # Supabase 'in' filter limit might apply.
        # Let's fetch ALL reactions since start date, then filter in python (easier if total reactions this week is low)
        reactions_resp = client.table("reactions").select("message_id, weight, created_at").gte("created_at", START_TIME_UTC).execute()
        
        if reactions_resp.data:
            for r in reactions_resp.data:
                # Check if this reaction is on one of the user's messages
                if r["message_id"] in user_msg_ids:
                    # Exclude self-reaction if logic requires?
                    # Bot logic: "if int(message["user_id"]) == int(payload.user_id): return"
                    # We need to know who reacted.
                    # Need to fetch 'user_id' (reactor) from table
                    pass 
        
        # Redo query to include reactor_id
        reactions_resp = client.table("reactions").select("message_id, user_id, weight").gte("created_at", START_TIME_UTC).execute()
        
        if reactions_resp.data:
            for r in reactions_resp.data:
                if r["message_id"] in user_msg_ids:
                     # Check self reaction
                     if r["user_id"] == user_id:
                         continue
                     
                     calc_reaction_score += float(r["weight"])
                     reaction_count += 1

    print(f"\n[Reactions Received]")
    print(f"Count: {reaction_count}")
    print(f"Calculated Score: {calc_reaction_score:.2f}")

    total_calculated = calc_msg_score + calc_reaction_score
    print(f"\n[Total Verification]")
    print(f"Calculated (Actual) Weekly Score: {total_calculated:.2f}")
    print(f"DB Weekly Score: {current_weekly_score}")
    print(f"Difference: {current_weekly_score - total_calculated:.2f}")

if __name__ == "__main__":
    asyncio.run(verify_score())
