
import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    print("Error: SUPABASE_URL or SUPABASE_KEY not set")
    exit(1)

client = create_client(url, key)

async def check_status():
    print("--- Checking Bot Metadata ---")
    try:
        metadata = client.table("bot_metadata").select("*").execute()
        if metadata.data:
            for item in metadata.data:
                print(f"Key: {item['key']}, Value: {item['value']}, Updated: {item['updated_at']}")
        else:
            print("No metadata found.")
    except Exception as e:
        print(f"Error fetching metadata: {e}")

    print("\n--- Current Weekly Leaderboard (Top 10) ---")
    try:
        users = client.table("users").select("username, current_score, weekly_score").order("weekly_score", desc=True).limit(10).execute()
        if users.data:
            print(f"{'Rank':<5} | {'Username':<20} | {'Weekly Score':<15} | {'Total Score':<15}")
            print("-" * 65)
            for i, user in enumerate(users.data, 1):
                print(f"{i:<5} | {user['username']:<20} | {user['weekly_score']:<15} | {user['current_score']:<15}")
        else:
            print("No users found.")
    except Exception as e:
        print(f"Error fetching users: {e}")

if __name__ == "__main__":
    asyncio.run(check_status())
