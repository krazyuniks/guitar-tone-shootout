"""Pytest configuration and fixtures."""

import os

# Set testing environment BEFORE any app imports
# This ensures TaskIQ uses InMemoryBroker
os.environ["TESTING"] = "1"
