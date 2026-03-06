# Tailscale Mobile Setup Guide

## 📱 Accessing OpenClaw Hub from iPhone

### 1. Install Tailscale App
- Download **Tailscale** from the App Store
- Sign in with your account
- Connect to your tailnet

### 2. Find Your Tailscale IP
On your Mac (openclaw-hub), run:
```bash
tailscale ip -4
```
Example: `100.107.120.47`

### 3. Access Services

**Your Tailscale IP:** `100.107.120.47`  
**Your Tailscale Hostname:** `openclaw-hub` (may require DNS fix)

**Primary Method (IP-based):**
```
http://100.107.120.47:18795/hub
```

**Alternative (Hostname, requires DNS setup):**
```
http://openclaw-hub:18795/hub
```

**Other Services:**
- Gateway: `http://100.107.120.47:18789`
- Voice Server: `http://100.107.120.47:18790/status`
- Token Tracker: `http://100.107.120.47:18794`
- Cron Dashboard: `http://100.107.120.47:18795/cron`
- Activity Hub: `http://100.107.120.47:18796`
- Vision Controller: `http://100.107.120.47:18799`
- MonoClaw: `http://100.107.120.47:18802`
- Raves: `http://100.107.120.47:3004`
- Arbitrage Scanner: `http://100.107.120.47:3005`

### 4. Apply ACL Configuration

Upload `tailscale-acl-fixed.json` to Tailscale Admin Console:

1. Go to https://login.tailscale.com/admin/acls
2. Replace the ACL with the contents of `tailscale-acl-fixed.json`
3. Click **Save**

The ACL allows your iPhone (`matthew-iphone`) to access all working services on `openclaw-hub`.

### 5. Add to Home Screen (iOS)

For quick access:
1. Open Mission Control Hub in Safari
2. Tap the **Share** button (⬆️ icon)
3. Scroll down and tap **Add to Home Screen**
4. Name it "OpenClaw Hub" or "Mission Control"
5. Tap **Add**

Now you have a native-like app icon on your home screen!

### 6. Mobile Features

The hub is optimized for mobile with:
- ✅ Touch-friendly buttons (44px minimum height)
- ✅ Responsive grid layout
- ✅ Sticky header for easy navigation
- ✅ Tap highlighting for feedback
- ✅ Landscape mode support
- ✅ No hover effects (touch-optimized)

### 7. DNS Fix (Optional - Use Hostname Instead of IP)

If you want to use `openclaw-hub` instead of `100.107.120.47`, run:

```bash
cd /Users/matthew/.openclaw/workspace
./fix-tailscale-dns.sh
```

This adds the hostname to `/etc/hosts` so DNS resolution works locally.

After running:
- MacBook: `http://openclaw-hub:18795/hub` ✅
- iPhone: `http://openclaw-hub:18795/hub` ✅ (may work automatically via MagicDNS)

### 8. Troubleshooting

**Can't connect?**
- Make sure Tailscale is connected (green checkmark in app)
- Verify your iPhone shows as `matthew-iphone` in Tailscale admin
- Check that the Mac is online and Tailscale is running

**401 Unauthorized errors?**
- Some services (like Jobs Dashboard port 18791) have Tailscale auth enabled
- These are intentionally excluded from the ACL
- Use the working services listed above

**Slow loading?**
- Tailscale can be slow on cellular
- Connect to WiFi for better performance
- Some dashboards load heavy data (Activity Hub, Token Tracker)

### 8. Updating ACL

If you add new services or change ports:

1. Edit `/Users/matthew/.openclaw/workspace/tailscale-acl-fixed.json`
2. Add the new port to the `dst` array under ACLs
3. Upload to Tailscale admin console
4. Wait 1-2 minutes for propagation

---

## 🔒 Security Notes

- All traffic is encrypted via Tailscale (WireGuard)
- Only your iPhone can access these services (ACL-restricted)
- No public internet exposure
- No need for VPN or port forwarding

---

## 📊 Recommended Home Screen Setup

**Folder: "OpenClaw"**
- Mission Control (main hub)
- Cron Dashboard (monitor tasks)
- Activity Hub (track activity)
- Raves (events)
- Arbitrage Scanner (markets)

All accessible on-the-go via Tailscale! 🦞
