# Night Sweep — approval quiz handling

After the nightly sweep ships its changes (committed, doctored, deployed, pushed),
`quiz()` sends Matthew a Telegram message with three inline buttons. Tapping one
delivers a **callback** to the agent of the form:

    nightsweep:<action>:<date>      e.g.  nightsweep:revert:2026-11-03

When you (any session) receive one of these, handle it as follows. The night's
details live in `nightsweep/reports/<date>.md` — it contains the commit line
(`Commit \`<sha>\``), the branch, the **Deployed** apps, and an exact
`## How to revert` command. Use that report as the source of truth.

## nightsweep:approve:<date>
Changes are kept. Just acknowledge ("Kept ✓ — nothing to undo."). No action.

## nightsweep:revert:<date>
Roll back that night's commit and redeploy the affected apps.
1. Read `nightsweep/reports/<date>.md`; grab the `<sha>`, the branch, and the
   **Deployed** app list.
2. `cd /root/MonoClaw && git revert --no-edit <sha> && git push origin HEAD:<branch>`
   (the report's `## How to revert` section has the exact command — prefer it).
3. Redeploy each app the report says was deployed (e.g. `railway up` in its dir,
   restart its systemd service, or re-export the web build — same `deploy_dir`
   mapping nightsweep.sh uses), and health-check each.
4. Confirm to Matthew what was reverted + redeployed.

## nightsweep:ask:<date>
Matthew wants to discuss the changes. Open `nightsweep/reports/<date>.md`, and
ask him what he'd like to know / change, then act on his answer.

Note: the buttons are a convenience layer. If a callback tap ever fails to route,
the report's `## How to revert` command still lets Matthew (or you) undo it by hand.
