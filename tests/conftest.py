"""
Pytest configuration for adversarial tests.
"""

import pytest

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
