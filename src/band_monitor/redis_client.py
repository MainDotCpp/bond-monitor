import redis.asyncio as redis
from typing import List, Set
import os
import json
import logging
from .models import Account
from .config import config

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self, host: str = "141.164.43.115", port: int = 6379, db: int = 0, password: str = "Haishi"):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.client = None
    
    async def connect(self):
        if not config.enable_sync:
            return
        if not self.client:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
        
        # 测试连接
        try:
            await self.client.ping()
        except Exception as e:
            # 连接失败，重置client并重新连接
            self.client = None
            raise e
    
    async def disconnect(self):
        if not config.enable_sync:
            return
        if self.client:
            await self.client.close()
    
    async def update_active_links(self, links: List[str]):
        if not config.enable_sync:
            return
        try:
            await self.connect()
            
            # Clear existing links
            await self.client.delete("links")
            
            # Add new links
            if links:
                await self.client.sadd("links", *links)
        except Exception as e:
            # 重置连接并重试一次
            self.client = None
            try:
                await self.connect()
                await self.client.delete("links")
                if links:
                    await self.client.sadd("links", *links)
            except Exception as retry_error:
                logger.error(f"Redis operation failed after retry: {retry_error}")
                raise
    
    async def get_active_links(self) -> Set[str]:
        if not config.enable_sync:
            return set()
        try:
            await self.connect()
            return await self.client.smembers("links")
        except Exception as e:
            # 重置连接并重试一次
            self.client = None
            try:
                await self.connect()
                return await self.client.smembers("links")
            except Exception as retry_error:
                logger.error(f"Redis get operation failed after retry: {retry_error}")
                return set()
    
    async def add_link(self, link: str):
        if not config.enable_sync:
            return
        try:
            await self.connect()
            await self.client.sadd("links", link)
        except Exception as e:
            self.client = None
            await self.connect()
            await self.client.sadd("links", link)
    
    async def remove_link(self, link: str):
        if not config.enable_sync:
            return
        try:
            await self.connect()
            await self.client.srem("links", link)
        except Exception as e:
            self.client = None
            await self.connect()
            await self.client.srem("links", link)

# Global Redis client instance
redis_client = RedisClient(
    host=os.getenv("REDIS_HOST", "141.164.43.115"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=int(os.getenv("REDIS_DB", "0")),
    password=os.getenv("REDIS_PASSWORD", "Haishi")
)