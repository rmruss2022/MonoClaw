#!/bin/bash
# Simple test script for quote generator

echo "Testing quote generator..."
bash quote.sh

if [ $? -eq 0 ]; then
    echo "✓ Test passed!"
else
    echo "✗ Test failed!"
    exit 1
fi
