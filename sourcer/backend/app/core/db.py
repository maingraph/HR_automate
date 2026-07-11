"""Supabase client singleton."""
from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client
from redis import Redis

from .config import settings


@lru_cache
def get_supabase() -> Client:
    key = settings.supabase_service_role_key or settings.supabase_anon_key
    if not settings.supabase_url or not key:
        raise RuntimeError("Supabase URL/KEY not configured")
    return create_client(settings.supabase_url, key)


@lru_cache
def get_redis() -> Redis:
    """Get Redis client for pub/sub and caching."""
    return Redis.from_url(settings.redis_url, decode_responses=True)
