#!/usr/bin/env python3
"""
Put a processed build in front of testers.

`eas submit` uploads a binary to App Store Connect and stops there. Assigning
it to a beta group is a separate API call, and without it the build processes
successfully, shows as VALID, and is invisible in TestFlight — which is exactly
how builds 17, 19 and 25 went missing while looking fine from the EAS side.

Usage:
    python3 testflight-release.py                # newest processed build
    python3 testflight-release.py 27             # a specific build number
    python3 testflight-release.py --wait 27      # wait for Apple to finish processing

Credentials come from ~/.openclaw/ios-creds (override with ASC_KEY_PATH).
Nothing is hardcoded to one machine.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

import jwt

BUNDLE_ID = os.environ.get("OPENHOME_BUNDLE_ID", "ai.openhome.app")
STORE = os.path.expanduser("~/.openclaw/ios-creds")
KEY_PATH = os.environ.get("ASC_KEY_PATH") or os.path.join(STORE, "asc-api-key.p8")


def meta(key, default=None):
    try:
        with open(os.path.join(STORE, "meta.json")) as fh:
            return json.load(fh).get(key, default)
    except OSError:
        return default


KEY_ID = os.environ.get("ASC_KEY_ID") or meta("asc_key_id")
ISSUER = os.environ.get("ASC_ISSUER") or meta("asc_issuer")


def token():
    now = int(time.time())
    with open(KEY_PATH) as fh:
        priv = fh.read()
    return jwt.encode(
        {"iss": ISSUER, "iat": now, "exp": now + 1100, "aud": "appstoreconnect-v1"},
        priv, algorithm="ES256", headers={"kid": KEY_ID, "typ": "JWT"},
    )


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request("https://api.appstoreconnect.apple.com" + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token())
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw else {})


def fail(msg):
    print("FAILED:", msg)
    sys.exit(1)


def main():
    args = [a for a in sys.argv[1:] if a != "--wait"]
    wait = "--wait" in sys.argv
    want = args[0] if args else None

    status, d = call("GET", f"/v1/apps?filter[bundleId]={BUNDLE_ID}")
    if status != 200 or not d.get("data"):
        fail(f"app lookup {status}: {d}")
    app_id = d["data"][0]["id"]
    print(f"app {BUNDLE_ID} -> {app_id}")

    # Newest first. processingState must be VALID before a group will take it.
    deadline = time.time() + (900 if wait else 0)
    while True:
        status, d = call("GET", f"/v1/builds?filter[app]={app_id}&limit=20&sort=-version")
        if status != 200:
            fail(f"build list {status}: {d}")
        builds = d.get("data", [])
        pick = None
        for b in builds:
            attrs = b["attributes"]
            if want and attrs.get("version") != str(want):
                continue
            if attrs.get("processingState") == "VALID":
                pick = b
                break
        if pick or time.time() >= deadline:
            break
        states = {b["attributes"].get("version"): b["attributes"].get("processingState") for b in builds[:4]}
        print(f"  waiting for Apple to finish processing: {states}")
        time.sleep(30)

    if not pick:
        have = {b["attributes"].get("version"): b["attributes"].get("processingState") for b in builds[:6]}
        fail(f"no VALID build{' ' + str(want) if want else ''}; saw {have}")

    number = pick["attributes"]["version"]
    print(f"build {number} is VALID ({pick['id']})")

    # Export compliance blocks distribution silently if unanswered.
    if pick["attributes"].get("usesNonExemptEncryption") is None:
        s, r = call("PATCH", f"/v1/builds/{pick['id']}",
                    {"data": {"type": "builds", "id": pick["id"],
                              "attributes": {"usesNonExemptEncryption": False}}})
        print(f"  export compliance set: {s}")

    status, d = call("GET", f"/v1/apps/{app_id}/betaGroups?limit=20")
    if status != 200:
        fail(f"group list {status}: {d}")
    groups = d.get("data", [])
    if not groups:
        fail("no beta groups on this app")

    assigned = []
    for g in groups:
        name = g["attributes"].get("name", "?")
        internal = g["attributes"].get("isInternalGroup")
        # External groups need App Review; only internal ones distribute instantly.
        if not internal:
            print(f"  skipping external group {name!r} (needs review)")
            continue
        s, r = call("POST", f"/v1/betaGroups/{g['id']}/relationships/builds",
                    {"data": [{"type": "builds", "id": pick["id"]}]})
        ok = s in (200, 201, 204)
        print(f"  {name!r}: {'assigned' if ok else f'FAILED {s} {r}'}")
        if ok:
            assigned.append(name)

    if not assigned:
        fail("build was not assigned to any internal group")
    print(f"\nbuild {number} is live in TestFlight for: {', '.join(assigned)}")


if __name__ == "__main__":
    main()
