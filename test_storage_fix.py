
import asyncio
import logging
import os
from dotenv import load_dotenv

# Setup minimal logging
logging.basicConfig(level=logging.INFO)

# Load env
load_dotenv()

# Check env before importing storage because config loads env
if not os.getenv("SUPABASE_URL"):
    print("Missing SUPABASE_URL")
    exit(1)

# Import storage
try:
    from src.storage import storage
except Exception as e:
    print(f"Failed to import storage: {e}")
    exit(1)

async def main():
    print("Testing get_metadata('last_weekly_reset_week')...")
    try:
        val = await storage.get_metadata("last_weekly_reset_week")
        print(f"Result: {val}")
    except AttributeError:
        print("FAIL: AttributeError - get_metadata not found!")
    except Exception as e:
        print(f"FAIL: {e}")

    # Don't test reset_weekly_scores here to avoid accidentally wiping data if user didn't want to yet?
    # User WANTS clarity.
    # But let's just confirm the method exists.
    if hasattr(storage, 'reset_weekly_scores'):
        print("PASS: reset_weekly_scores method exists on storage object.")
    else:
        print("FAIL: reset_weekly_scores method MISSING.")

if __name__ == "__main__":
    asyncio.run(main())
