from pydantic import BaseModel
from typing import Optional
from enum import Enum

class MonitorStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused" 
    STOPPED = "stopped"

class Account(BaseModel):
    id: Optional[int] = None
    username: str
    password: str
    status: MonitorStatus = MonitorStatus.STOPPED
    friend_count: int = 0  # 好友增量（实际增加的好友数）
    # 当前数量
    current_friend_count: int = 0
    current_friend_requests: int = 0
    # 初始数量（开始监控时记录）
    initial_friend_count: int = 0
    initial_friend_requests: int = 0
    last_updated: Optional[str] = None
    band_id: Optional[str] = None
    band_name: Optional[str] = None
    target_friend_count: int = 10  # 目标增量
    notes: Optional[str] = None
    
    # 向后兼容：返回当前好友总数
    @property  
    def current_total_count(self) -> int:
        return self.current_friend_count
    
    # 进度计算属性
    @property
    def initial_total(self) -> int:
        """初始总数（好友 + 请求）"""
        return self.initial_friend_count + self.initial_friend_requests
    
    @property
    def current_total(self) -> int:
        """当前总数（好友 + 请求）"""
        return self.current_friend_count + self.current_friend_requests
    
    @property
    def progress_gained(self) -> int:
        """已获得的进度"""
        return max(0, self.current_total - self.initial_total)
    
    @property
    def progress_needed(self) -> int:
        """总共需要的进度（目标增量）"""
        return max(0, self.target_friend_count)
    
    @property
    def progress_percentage(self) -> float:
        """进度百分比"""
        if self.progress_needed <= 0:
            return 100.0 if self.target_friend_count > 0 else 0.0
        return min(100.0, (self.progress_gained / self.progress_needed) * 100.0)
    
    @property
    def is_target_reached(self) -> bool:
        """是否达到目标"""
        return self.current_total >= self.target_friend_count if self.target_friend_count > 0 else False

class AccountCreate(BaseModel):
    username: str
    password: str

class MonitorResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None