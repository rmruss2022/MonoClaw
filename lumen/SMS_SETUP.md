# Lumen — SMS setup & the one remaining step (A2P 10DLC)

Everything in the app is built, deployed, and verified. The Twilio send path works
(test messages are **accepted** by Twilio). The only blocker to real delivery is
US carrier registration, which must be done by a human in the Twilio Console.

## Status

- ✅ Code shipped (`send_sms`, signup phone+consent, STOP webhook w/ signature
  validation, in-app settings, lifecycle engine `sms_tick`).
- ✅ Railway env set: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER=+19547588252`.
- ✅ `SMS_MODE=dryrun` (default) — engine logs who *would* get a text, sends nothing.
- 🚫 **Delivery blocked: error 30034** — number not registered for US A2P 10DLC.
- ⚠️ **Rotate the Twilio auth token** — it was pasted in chat. Twilio Console →
  Account → API keys & tokens → rotate; then update
  `/root/.openclaw/credentials/twilio.env` and the Railway var.

## Fix: register A2P 10DLC (~15 min of forms, then carrier approval)

Twilio Console → **Messaging → Regulatory Compliance → A2P 10DLC**:

1. **Register a Brand** (the business behind the texts).
   - Sole proprietor path = fastest/cheapest for low volume (no EIN needed; uses
     your name + mobile for OTP). Standard/Low-Volume Standard if you have an EIN.
2. **Create a Campaign.** Suggested answers:
   - **Use case:** Mixed / Low Volume Mixed (lifecycle + account notifications).
   - **Description:** "Lumen sends opt-in meditation practice reminders, streak-save
     nudges, and re-engagement messages to users who provided their mobile number
     and checked the SMS consent box at signup or in app settings."
   - **Sample message 1:** "Matthew, your 5-day streak on Lumen is still lit — one
     short sit before midnight keeps it going. Reply STOP to opt out."
   - **Sample message 2:** "Your light has been waiting on Lumen. Two quiet minutes
     is a real beginning — come sit with us again. Reply STOP to opt out."
   - **Opt-in:** "Users opt in by entering their mobile number and checking a
     consent checkbox at signup or in Profile → Text reminders. Consent language:
     'Text me gentle practice reminders. Msg & data rates may apply; reply STOP
     anytime to opt out.'"
   - **Opt-out:** "Users reply STOP; handled via Twilio + our /api/sms/inbound webhook."
   - **Help:** "Users reply HELP."
3. **Attach number** `+19547588252` to the Messaging Service / campaign.
4. Wait for campaign **approved** (minutes–hours, sometimes a day).

## Then go live

1. Point the Twilio number's **inbound webhook** at the app so STOP/START sync:
   `https://lumen-production-a8c6.up.railway.app/api/sms/inbound` (HTTP POST).
   (The app validates `X-Twilio-Signature`, so set the webhook URL exactly.)
2. Flip the engine on: `railway variables --set "SMS_MODE=live"` (redeploys).
3. Smoke test from an owner account: `POST /api/admin/sms/test {"to":"+1..."}`.

## OpenClaw agent SMS (deferred — needs its own number)

The official `@openclaw/sms` plugin points the Twilio number's inbound webhook at
the **Gateway** (`/webhooks/sms`). That **collides** with Lumen's STOP webhook on
the same number — one number can't serve both. Decision: **this number is
dedicated to Lumen.** To put the agent on SMS, buy a second Twilio number and run
the plugin against that one.
