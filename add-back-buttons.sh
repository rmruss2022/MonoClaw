#!/bin/bash

# Add back buttons to all dashboards

BACK_BUTTON_CSS='        .back-button {
            position: fixed;
            top: 20px;
            left: 20px;
            background: rgba(0, 217, 255, 0.1);
            border: 1px solid rgba(0, 217, 255, 0.3);
            padding: 10px 20px;
            border-radius: 8px;
            color: #00d9ff;
            text-decoration: none;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.2s;
            z-index: 1000;
        }
        .back-button:hover {
            background: rgba(0, 217, 255, 0.2);
            transform: translateX(-3px);
            box-shadow: 0 0 20px rgba(0, 217, 255, 0.3);
        }'

BACK_BUTTON_HTML='    <a href="http://localhost:18795/hub" class="back-button">
        ← Back to Command Hub
    </a>'

# List of dashboard files
DASHBOARDS=(
    "/Users/matthew/.openclaw/workspace/jobs/dashboard.html"
    "/Users/matthew/.openclaw/workspace/raves/dashboard.html"
    "/Users/matthew/.openclaw/workspace/moltbook-dashboard/dashboard.html"
)

for dashboard in "${DASHBOARDS[@]}"; do
    if [ -f "$dashboard" ]; then
        echo "Processing $dashboard..."
        
        # Check if back button CSS already exists
        if ! grep -q "\.back-button" "$dashboard"; then
            # Add CSS before </style>
            perl -i -pe 's|(</style>)|'"$(echo "$BACK_BUTTON_CSS" | sed 's/[&/\]/\\&/g')"'\n        $1|' "$dashboard"
            echo "  ✓ Added CSS"
        else
            echo "  - CSS already exists"
        fi
        
        # Check if back button HTML already exists
        if ! grep -q "Back to Command Hub" "$dashboard"; then
            # Add HTML after <body>
            perl -i -pe 's|(<body>)|\1\n'"$(echo "$BACK_BUTTON_HTML" | sed 's/[&/\]/\\&/g')"'\n|' "$dashboard"
            echo "  ✓ Added HTML"
        else
            echo "  - HTML already exists"
        fi
        
        echo ""
    else
        echo "⚠️  File not found: $dashboard"
    fi
done

echo "✅ Done! Back buttons added to all dashboards."
