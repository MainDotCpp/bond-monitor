import asyncio
from typing import List, Set
from .database import Database
from .browser_manager import BrowserManager
from .redis_client import redis_client
import logging
from .config import config

logger = logging.getLogger(__name__)

class LinkManager:
    def __init__(self, db: Database, browser_manager: BrowserManager):
        self.db = db
        self.browser_manager = browser_manager
        self.update_task = None
        self.is_running = False
        self._cached_links: Set[str] = set()
        self._update_frequency = 30  # 默认30秒
        self._min_frequency = 5      # 最小5秒
    
    async def get_active_links(self) -> List[str]:
        """获取当前活跃链接 - 正在运行且在成员页面且未达到目标friend_count"""
        links = []
        active_accounts = await self.db.get_active_accounts()
        
        for account in active_accounts:
            # 优先使用保存的link，如果没有则使用band_id生成
            if account.link:
                # 检查浏览器是否在成员页面
                status = await self.browser_manager.check_browser_and_page_status(account.id)
                if status.get('on_member_page', False):
                    links.append(account.link)
            elif account.band_id:
                # 兼容原有逻辑，使用band_id生成链接
                status = await self.browser_manager.check_browser_and_page_status(account.id)
                if status.get('on_member_page', False):
                    member_url = f"https://band.us/band/{account.band_id}/member"
                    links.append(member_url)
        
        return links
    
    async def update_redis_links(self, force: bool = False):
        if not config.enable_sync:
            return False
        """更新Redis中的链接"""
        try:
            active_links = await self.get_active_links()
            current_links = set(active_links)
            
            # 只有在链接发生变化或强制更新时才更新Redis
            if force or current_links != self._cached_links:
                await redis_client.update_active_links(active_links)
                self._cached_links = current_links
                logger.info(f"Updated Redis with {len(active_links)} active links")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to update Redis links: {e}")
            return False
    
    async def trigger_immediate_update(self):
        if not config.enable_sync:
            return
        """触发立即更新（事件驱动）"""
        if not self.is_running:
            return
        
        try:
            # 立即更新一次
            updated = await self.update_redis_links(force=False)
            if updated:
                logger.info("Immediate Redis update triggered")
        except Exception as e:
            logger.error(f"Failed to trigger immediate update: {e}")
    
    async def start_periodic_update(self, interval: int = 30):
        if not config.enable_sync:
            return
        """启动定期更新任务"""
        if self.is_running:
            return
        
        self.is_running = True
        self._update_frequency = interval
        
        async def update_loop():
            consecutive_no_changes = 0
            current_interval = interval
            
            while self.is_running:
                try:
                    updated = await self.update_redis_links()
                    
                    # 动态调整更新频率
                    if updated:
                        # 有变化时，重置到默认频率
                        consecutive_no_changes = 0
                        current_interval = max(self._min_frequency, interval // 2)  # 稍微提高频率
                    else:
                        consecutive_no_changes += 1
                        # 连续无变化时，逐渐降低频率，但不超过原始间隔的2倍
                        if consecutive_no_changes > 3:
                            current_interval = min(interval * 2, current_interval * 1.2)
                    
                    await asyncio.sleep(current_interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in link update loop: {e}")
                    await asyncio.sleep(interval)
        
        self.update_task = asyncio.create_task(update_loop())
    
    async def stop_periodic_update(self):
        """停止定期更新任务"""
        self.is_running = False
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
            self.update_task = None
    
    async def force_update(self):
        if not config.enable_sync:
            return
        """立即更新一次"""
        await self.update_redis_links(force=True)