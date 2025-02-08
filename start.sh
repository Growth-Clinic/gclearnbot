#!/bin/bash

# Exit on error
set -e

# Load environment variables from .env if it exists (for local development)
if [ -f .env ]; then
    echo "Loading environment from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Check if required environment variables are set (either from .env or Render)
required_vars=(
    "TELEGRAM_BOT_TOKEN"
    "MONGODB_URI"
    "WEBHOOK_URL"
    "SLACK_BOT_TOKEN"
    "SLACK_SIGNING_SECRET"
    "SLACK_APP_TOKEN"
)

missing_vars=0
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: $var is not set!"
        missing_vars=1
    fi
done

if [ $missing_vars -eq 1 ]; then
    echo "Please set all required environment variables"
    exit 1
fi

# Run the bot
echo "Starting bot..."
python main.py || {
    echo "Error: Failed to start bot!"
    exit 1
}