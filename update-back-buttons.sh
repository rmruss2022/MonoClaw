#!/bin/bash

# Update all back buttons to floating action button style (bottom-right)

BACK_BUTTON_CSS='        .back-button {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: rgba(0, 217, 255, 0.15);
            border: 2px solid rgba(0, 217, 255, 0.4);
            padding: 12px 24px;
            border-radius: 50px;
            color: #00d9ff;
            text-decoration: none;
            font-weight: 600;
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
            z-index: 9999;
            box-shadow: 0 4px 15px rgba(0, 217, 255, 0.2);
            backdrop-filter: blur(10px);
        }
        .back-button:hover {
            background: rgba(0, 217, 255, 0.25);
            transform: translateY(-3px);
            box-shadow: 0 6px 25px rgba(0, 217, 255, 0.4);
            border-color: rgba(0, 217, 255, 0.6);
        }
        .back-button::before {
            content: "←";
            font-size: 1.2rem;
        }'

# Files to update
FILES=(
    "/Users/matthew/.openclaw/workspace/tokens/dashboard.html"
    "/Users/matthew/.openclaw/workspace/jobs/dashboard.html"
    "/Users/matthew/.openclaw/workspace/raves/dashboard.html"
    "/Users/matthew/.openclaw/workspace/moltbook-dashboard/dashboard.html"
    "/Users/matthew/.openclaw/voice-server/server.js"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "Updating $file..."
        
        # Remove old back-button CSS block
        perl -i -0pe 's/\.back-button \{[^}]*\}[^}]*\.back-button:hover \{[^}]*\}//gs' "$file"
        
        # Add new CSS before first closing </style> tag
        perl -i -pe 's|(</style>)|'"$(echo "$BACK_BUTTON_CSS" | sed 's/[&/\]/\\&/g; s/$/\\n/g' | tr -d '\n')"'\n        $1|' "$file"
        
        # Update HTML - remove old button text content
        perl -i -pe 's|(href="http://localhost:18795/hub" class="back-button">)[^<]*(<)|$1Hub$2|g' "$file"
        
        echo "  ✓ Updated"
    else
        echo "  ⚠️  Not found: $file"
    fi
done

echo ""
echo "✅ All back buttons updated to floating action button style!"
echo "   Position: Bottom-right corner"
echo "   Style: Compact pill button with backdrop blur"
