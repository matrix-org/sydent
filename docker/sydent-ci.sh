#!/usr/bin/env bash

# Install any new dependencies
pip install -e .

# Start Sydent and run for 5s
timeout 5s python -m sydent.sydent

# Check that it started up correctly
if [ $? -eq 124 ]; then
  # Timeout got it, so it must've been running correctly
  echo "Sydent startup up successfully"
  exit 0
else
  # Sydent exited before the timeout. Something went wrong
  echo "Sydent failed to start"
  echo 1
fi
