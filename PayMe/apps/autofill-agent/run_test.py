"""Standalone test runner — reads test.md and runs the autofill job."""
import asyncio
import sys
import os
import uuid

# Make the autofill package importable
sys.path.insert(0, os.path.dirname(__file__))

from autofill.browser import run_autofill_job

USER_DATA = {
    "first_name": "Matthew",
    "last_name": "Russell",
    "email": "mattrussellc@gmail.com",
    "phone": "2017837383",
    "address": "30 Louise Ct",
    "city": "Allendale",
    "state": "NJ",
    "state_full": "New Jersey",
    "zip": "07401",
    "dob": "",
    "gender": "Male",
}

JOB_DATA = {
    "id": str(uuid.uuid4()),
    "claim_url": "https://veritaconnect.com/subscriptionmembershipsettlement",
    "settlement_title": "Subscription Membership Settlement",
}


async def main():
    print(f"[run_test] Starting autofill job {JOB_DATA['id']}")
    print(f"[run_test] URL: {JOB_DATA['claim_url']}")
    try:
        results = await run_autofill_job(JOB_DATA, USER_DATA)
        print("\n=== RESULTS ===")
        for step, result in results.items():
            status = result.get("status", "?")
            print(f"  {step}: {status}")
            if result.get("error"):
                print(f"    ERROR: {result['error']}")
            if result.get("storage_key"):
                print(f"    Screenshot: {result['storage_key']}")
            if result.get("confirmed"):
                print(f"    CONFIRMED SUBMISSION: {result.get('body_snippet', '')[:150]}")
        print("\n[run_test] Done.")
    except Exception as e:
        print(f"[run_test] FAILED: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
