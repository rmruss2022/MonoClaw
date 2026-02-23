"""Browser automation module for the autofill agent — Track 4.

Vision-LLM driven loop:
  1. navigate    — load URL through nodriver (bypasses Cloudflare Turnstile)
  2. vision loop — screenshot → Claude vision → JS execution → repeat
  3. submit      — detect confirmation page and return results

The LLM decides what JavaScript to run at each step, handling arbitrary
form structures, CAPTCHAs, and multi-page flows without hardcoded selectors.

Raises:
    BlockedError: if definitively blocked with no recovery path.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autofill.settings import worker_settings


class BlockedError(Exception):
    """Raised when the claim page is definitively blocked."""


# ---------------------------------------------------------------------------
# React-compatible fill helper (included in every LLM-generated JS snippet)
# ---------------------------------------------------------------------------

_REACT_HELPERS_JS = """
// React-compatible setters — works on controlled components
function _setInputValue(el, val) {
    el.focus();
    var d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
    if (d && d.set) { d.set.call(el, val); } else { el.value = val; }
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
    el.blur();
}
function _setTextareaValue(el, val) {
    el.focus();
    var d = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
    if (d && d.set) { d.set.call(el, val); } else { el.value = val; }
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
    el.blur();
}
function _setSelectValue(el, val) {
    var d = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value');
    if (d && d.set) { d.set.call(el, val); } else { el.value = val; }
    el.dispatchEvent(new Event('change', {bubbles: true}));
}
function _checkCheckbox(cb) {
    var d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'checked');
    if (d && d.set) { d.set.call(cb, true); } else { cb.checked = true; }
    cb.dispatchEvent(new Event('click', {bubbles: true}));
    cb.dispatchEvent(new Event('change', {bubbles: true}));
    cb.dispatchEvent(new Event('input', {bubbles: true}));
}
function _clickButton(text) {
    var btns = document.querySelectorAll('button, input[type=submit]');
    for (var i = 0; i < btns.length; i++) {
        var b = btns[i];
        if (b.disabled) continue;
        var t = (b.textContent || b.value || '').trim().toLowerCase();
        if (t.indexOf(text.toLowerCase()) >= 0) {
            b.scrollIntoView({behavior: 'instant', block: 'center'});
            b.click();
            return 'clicked:' + t;
        }
    }
    return 'not_found';
}
"""

# ---------------------------------------------------------------------------
# LLM vision call
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an intelligent browser automation agent filling out a legal settlement claim form.

USER DATA (use exactly these values):
{user_data_json}

YOUR MISSION: Fill out every required field on the visible form and submit it.

RESPOND WITH VALID JSON ONLY — no markdown, no explanation outside JSON:
{{
  "status": "filling" | "waiting_for_captcha" | "submitted" | "blocked",
  "observations": "brief description of what you see",
  "js": "JavaScript code to execute (empty string if status is submitted/blocked/waiting_for_captcha)"
}}

RULES FOR WRITING THE JS:
1. The helpers _setInputValue(el, val), _setTextareaValue(el, val), _setSelectValue(el, val),
   _checkCheckbox(cb), _clickButton(text) are already defined — use them.
2. Find inputs by label text: document.querySelector('label') whose textContent includes the field name,
   then use the label's 'for' attribute to get the input id, OR search by placeholder/name/aria-label.
3. NEVER fill fields whose label contains: "pitch", "haiku", "fax", "leave blank", "do not fill", "ai agent".
4. Check ALL eligibility/qualification checkboxes — the user qualifies for everything.
5. After filling visible fields, call _clickButton('Continue') or _clickButton('Submit') to advance.
6. If you see a Cloudflare Turnstile or loading screen, set status to "waiting_for_captcha".
7. If you see "Thank you", "Confirmation", "Claim ID", "Successfully submitted" → set status to "submitted".
8. For SELECT elements (dropdowns), find the matching option by text.
9. For radio buttons: r.click() + r.dispatchEvent(new Event('change', {{bubbles:true}})).
10. Keep JS concise — do everything needed in a single block, then click the advance button.
"""


async def _llm_page_action(
    screenshot_path: Path,
    page_text: str,
    user_data: dict,
    history: list[str],
) -> dict:
    """Send screenshot + context to Claude vision and get back a structured action."""
    import anthropic
    import os

    api_key = worker_settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    # Encode screenshot
    img_data = base64.standard_b64encode(screenshot_path.read_bytes()).decode()

    system = _SYSTEM_PROMPT.format(user_data_json=json.dumps(user_data, indent=2))

    history_text = "\n".join(history[-4:]) if history else "No previous steps."
    user_text = (
        f"Recent steps:\n{history_text}\n\n"
        f"Current page text (first 800 chars):\n{page_text[:800]}\n\n"
        "What should I do next? Return JSON only."
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=system,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_data,
                        },
                    },
                    {"type": "text", "text": user_text},
                ],
            }
        ],
    )

    raw = response.content[0].text.strip()
    print(f"  [llm] raw response: {raw[:300]}")

    # Parse JSON — handle markdown fences
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract first JSON object
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return {"status": "filling", "observations": "JSON parse failed", "js": ""}


async def _human_delay(min_ms: int = 200, max_ms: int = 600) -> None:
    await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_autofill_job(job_data: dict, user_data: dict) -> dict[str, Any]:
    """Execute autofill using nodriver + Claude vision loop."""
    import nodriver as uc

    artifacts_dir = Path(worker_settings.autofill_artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    claim_url: str = job_data.get("claim_url") or ""
    job_id: str = str(job_data.get("id", "unknown"))
    step_results: dict[str, Any] = {}

    if not claim_url:
        step_results["navigate"] = {"status": "failed", "error": "claim_url is empty"}
        raise BlockedError("No claim URL provided.")

    # Persistent profile so CF recognises the browser as a returning user
    profile_dir = Path("/tmp/autofill-chrome-profile")
    profile_dir.mkdir(parents=True, exist_ok=True)

    browser = await uc.start(
        headless=False,
        browser_executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        user_data_dir=str(profile_dir),
        browser_args=[
            "--window-size=1280,900",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
        ],
    )

    try:
        tab = await browser.get(claim_url)
        await asyncio.sleep(5)  # Initial CF window

        # ------------------------------------------------------------------
        # Wait for Cloudflare to resolve (up to 90 s)
        # ------------------------------------------------------------------
        for attempt in range(30):
            title = await tab.evaluate("document.title")
            print(f"  [CF] attempt={attempt} title={title!r}")
            if title and any(w in title.lower() for w in ["just a moment", "checking", "attention required"]):
                await asyncio.sleep(3)
            else:
                break
        else:
            raise BlockedError("Cloudflare challenge did not resolve after 90 s.")

        step_results["navigate"] = {"status": "done", "url": claim_url}

        # ------------------------------------------------------------------
        # Inject React helpers once after page load
        # ------------------------------------------------------------------
        await tab.evaluate(_REACT_HELPERS_JS)

        # ------------------------------------------------------------------
        # Vision-LLM loop
        # ------------------------------------------------------------------
        history: list[str] = []
        final_ss_path: Path | None = None
        confirmed = False
        max_steps = 20

        for step_num in range(max_steps):
            await asyncio.sleep(2.5)

            # Re-inject helpers (may have been lost after navigation)
            try:
                await tab.evaluate(_REACT_HELPERS_JS)
            except Exception:
                pass

            # Screenshot
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            ss_path = artifacts_dir / f"autofill_{job_id}_step{step_num}_{ts}.png"
            try:
                await tab.save_screenshot(str(ss_path))
                final_ss_path = ss_path
                print(f"  [screenshot] {ss_path}")
            except Exception as exc:
                print(f"  [screenshot] failed: {exc}")
                continue

            # Page text
            try:
                page_text = await tab.evaluate("document.body.innerText")
            except Exception:
                page_text = ""
            page_url = await tab.evaluate("window.location.href")
            print(f"  [step{step_num}] url={page_url}")
            print(f"  [step{step_num}] text[:120]={page_text[:120]!r}")

            # Fast-path confirmation check
            confirmed_words = [
                "thank you", "confirmation number", "successfully submitted",
                "your claim has been", "claim has been filed", "claim has been received",
                "claim id:", "reference number", "submission complete",
            ]
            if any(w in page_text.lower() for w in confirmed_words):
                confirmed = True
                history.append(f"Step {step_num}: CONFIRMED submission")
                break

            # Ask the LLM what to do
            action = await _llm_page_action(ss_path, page_text, user_data, history)
            obs = action.get("observations", "")
            status = action.get("status", "filling")
            js_code = action.get("js", "")

            history.append(f"Step {step_num}: {obs[:120]} | status={status}")
            print(f"  [llm] status={status} obs={obs[:100]}")

            if status == "submitted":
                confirmed = True
                break

            if status == "blocked":
                step_results["submit"] = {
                    "status": "failed",
                    "confirmed": False,
                    "body_snippet": page_text[:300],
                    "error": obs,
                }
                break

            if status == "waiting_for_captcha":
                print("  [captcha] waiting for CAPTCHA to auto-resolve...")
                await asyncio.sleep(8)
                continue

            # Execute the LLM's JS
            if js_code:
                full_js = _REACT_HELPERS_JS + "\n" + js_code
                try:
                    result = await tab.evaluate(full_js)
                    print(f"  [js] result={str(result)[:120]}")
                except Exception as exc:
                    print(f"  [js] error: {exc}")
                await _human_delay(400, 800)

        # ------------------------------------------------------------------
        # Final results
        # ------------------------------------------------------------------
        step_results.setdefault("fill_form", {"status": "done"})
        if final_ss_path:
            step_results.setdefault("screenshot", {
                "status": "done",
                "storage_key": str(final_ss_path),
                "size_bytes": final_ss_path.stat().st_size if final_ss_path.exists() else 0,
            })

        if not confirmed:
            page_text = (await tab.evaluate("document.body.innerText")).lower()
            confirmed = any(w in page_text for w in confirmed_words)

        step_results["submit"] = {
            "status": "done",
            "confirmed": confirmed,
            "body_snippet": (await tab.evaluate("document.body.innerText"))[:400],
        }

    finally:
        try:
            browser.stop()
        except Exception:
            pass

    return step_results
