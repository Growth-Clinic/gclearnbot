#!/bin/bash

# Exit on error
set -e

# Load environment
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "Error: .env file not found!"
    exit 1
fi

# Run the bot
python gc_learn_bot.py || {
    echo "Error: Failed to start bot!"
    exit 1
}