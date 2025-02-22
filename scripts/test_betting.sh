#!/bin/bash

# Ensure we're in the project root
cd "$(dirname "$0")/.."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the tests
echo "Running betting research flow tests..."
python -m app.tests.test_betting_flow

# Check if tests passed
if [ $? -eq 0 ]; then
    echo "✅ All tests completed successfully!"
else
    echo "❌ Tests failed!"
    exit 1
fi 