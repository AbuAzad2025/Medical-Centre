"""Caching configuration for the medical platform."""

from __future__ import annotations

import os

from flask import Flask
from flask_caching import Cache

# Cache configuration
CACHE_TYPE = os.environ.get('CACHE_TYPE', 'SimpleCache')  # SimpleCache for dev, RedisCache for prod
CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', '300'))  # 5 minutes
CACHE_REDIS_URL = os.environ.get('REDIS_URL', None)

cache_config = {
    'CACHE_TYPE': CACHE_TYPE,
    'CACHE_DEFAULT_TIMEOUT': CACHE_DEFAULT_TIMEOUT,
}

if CACHE_TYPE == 'RedisCache' and CACHE_REDIS_URL:
    cache_config['CACHE_REDIS_URL'] = CACHE_REDIS_URL

cache = Cache()


def init_cache(app: Flask) -> None:
    """Initialize caching for the Flask app."""
    app.config.update(cache_config)
    cache.init_app(app)
    app.logger.info(f'Cache initialized: {CACHE_TYPE} (timeout={CACHE_DEFAULT_TIMEOUT}s)')
