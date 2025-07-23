import aiosqlite
import asyncio
from typing import List, Optional
from .models import Account, MonitorStatus

class Database:
    def __init__(self, db_path: str = "band_monitor.db"):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Create table with original schema first
            await db.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    status TEXT DEFAULT 'stopped',
                    friend_count INTEGER DEFAULT 0,
                    last_updated TEXT
                )
            """)
            
            # Check for new columns and add them if missing
            cursor = await db.execute("PRAGMA table_info(accounts)")
            columns = await cursor.fetchall()
            column_names = [column[1] for column in columns]
            
            new_columns = {
                'band_id': 'TEXT',
                'band_name': 'TEXT',
                'current_friend_count': 'INTEGER DEFAULT 0',
                'current_friend_requests': 'INTEGER DEFAULT 0', 
                'initial_friend_count': 'INTEGER DEFAULT 0',
                'initial_friend_requests': 'INTEGER DEFAULT 0',
                'target_friend_count': 'INTEGER DEFAULT 10',
                'notes': 'TEXT'
            }
            
            for column_name, column_type in new_columns.items():
                if column_name not in column_names:
                    await db.execute(f"ALTER TABLE accounts ADD COLUMN {column_name} {column_type}")
            
            # Migrate existing friend_count to current_friend_count if needed
            if 'current_friend_count' not in column_names and 'friend_count' in column_names:
                await db.execute("UPDATE accounts SET current_friend_count = friend_count WHERE current_friend_count IS NULL")
            
            # Update existing accounts with default target_friend_count if it's 0 or NULL
            await db.execute("UPDATE accounts SET target_friend_count = 10 WHERE target_friend_count IS NULL OR target_friend_count = 0")
            
            await db.commit()

    async def add_account(self, username: str, password: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO accounts (username, password, target_friend_count) VALUES (?, ?, 10)",
                (username, password)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_account(self, account_id: int) -> Optional[Account]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row  # Enable named access
            cursor = await db.execute(
                "SELECT * FROM accounts WHERE id = ?", (account_id,)
            )
            row = await cursor.fetchone()
            if row:
                # Use safe dictionary-style access for sqlite Row
                def safe_get(row, key, default=None):
                    try:
                        return row[key] if key in row.keys() else default
                    except (KeyError, IndexError):
                        return default
                
                account_data = {
                    "id": row["id"],
                    "username": row["username"], 
                    "password": row["password"],
                    "status": MonitorStatus(row["status"]),
                    "last_updated": row["last_updated"],
                    "friend_count": safe_get(row, "friend_count", 0) or 0,
                    "band_id": safe_get(row, "band_id"),
                    "band_name": safe_get(row, "band_name"),
                    "current_friend_count": safe_get(row, "current_friend_count") or safe_get(row, "friend_count", 0) or 0,
                    "current_friend_requests": safe_get(row, "current_friend_requests", 0) or 0,
                    "initial_friend_count": safe_get(row, "initial_friend_count", 0) or 0,
                    "initial_friend_requests": safe_get(row, "initial_friend_requests", 0) or 0,
                    "target_friend_count": safe_get(row, "target_friend_count", 10),
                    "notes": safe_get(row, "notes"),
                }
                
                return Account(**account_data)
            return None

    async def get_all_accounts(self) -> List[Account]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row  # Enable named access
            cursor = await db.execute("SELECT * FROM accounts")
            rows = await cursor.fetchall()
            accounts = []
            for row in rows:
                # Use safe dictionary-style access for sqlite Row
                def safe_get(row, key, default=None):
                    try:
                        return row[key] if key in row.keys() else default
                    except (KeyError, IndexError):
                        return default
                
                account_data = {
                    "id": row["id"],
                    "username": row["username"], 
                    "password": row["password"],
                    "status": MonitorStatus(row["status"]),
                    "last_updated": row["last_updated"],
                    "friend_count": safe_get(row, "friend_count", 0) or 0,
                    "band_id": safe_get(row, "band_id"),
                    "band_name": safe_get(row, "band_name"),
                    "current_friend_count": safe_get(row, "current_friend_count") or safe_get(row, "friend_count", 0) or 0,
                    "current_friend_requests": safe_get(row, "current_friend_requests", 0) or 0,
                    "initial_friend_count": safe_get(row, "initial_friend_count", 0) or 0,
                    "initial_friend_requests": safe_get(row, "initial_friend_requests", 0) or 0,
                    "target_friend_count": safe_get(row, "target_friend_count", 10),
                    "notes": safe_get(row, "notes"),
                }
                
                accounts.append(Account(**account_data))
            return accounts

    async def update_account_status(self, account_id: int, status: MonitorStatus):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE accounts SET status = ? WHERE id = ?",
                (status.value, account_id)
            )
            await db.commit()

    async def update_friend_count(self, account_id: int, count: int, timestamp: str):
        """向后兼容的方法"""
        await self.update_current_counts(account_id, count, None, timestamp)
    
    async def update_current_counts(self, account_id: int, friend_count: int, friend_requests: int, timestamp: str):
        async with aiosqlite.connect(self.db_path) as db:
            # 先获取初始计数来计算增量
            cursor = await db.execute(
                "SELECT initial_friend_count, initial_friend_requests FROM accounts WHERE id = ?", 
                (account_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                initial_friend_count = row[0] or 0
                initial_friend_requests = row[1] or 0
                initial_total = initial_friend_count + initial_friend_requests
                
                # 计算当前总数和增量
                if friend_requests is not None:
                    current_total = friend_count + friend_requests
                    increment = max(0, current_total - initial_total)
                    
                    await db.execute(
                        "UPDATE accounts SET current_friend_count = ?, current_friend_requests = ?, friend_count = ?, last_updated = ? WHERE id = ?",
                        (friend_count, friend_requests, increment, timestamp, account_id)
                    )
                else:
                    # 如果只有好友数，假设请求数为0来计算增量
                    current_total = friend_count
                    increment = max(0, current_total - initial_total)
                    
                    await db.execute(
                        "UPDATE accounts SET current_friend_count = ?, friend_count = ?, last_updated = ? WHERE id = ?",
                        (friend_count, increment, timestamp, account_id)
                    )
            
            await db.commit()
    
    async def set_initial_counts(self, account_id: int, friend_count: int, friend_requests: int):
        """
        设置或更新账户的好友计数
        - 如果初始值未设置（为0或NULL），则设置初始值，并将friend_count重置为0
        - 如果初始值已设置，则只更新当前值，并重新计算friend_count增量
        """
        async with aiosqlite.connect(self.db_path) as db:
            # 检查是否已有初始值
            cursor = await db.execute(
                "SELECT initial_friend_count, initial_friend_requests FROM accounts WHERE id = ?",
                (account_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                initial_friend_count = row[0] or 0
                initial_friend_requests = row[1] or 0
                initial_total = initial_friend_count + initial_friend_requests
                
                # 只有初始值未设置时才设置初始值
                if initial_total == 0:
                    print(f"Account {account_id}: Setting initial counts - friends: {friend_count}, requests: {friend_requests}")
                    await db.execute(
                        "UPDATE accounts SET initial_friend_count = ?, initial_friend_requests = ?, current_friend_count = ?, current_friend_requests = ?, friend_count = 0 WHERE id = ?",
                        (friend_count, friend_requests, friend_count, friend_requests, account_id)
                    )
                else:
                    # 如果已有初始值，只更新当前值并重新计算增量
                    current_total = friend_count + friend_requests
                    increment = max(0, current_total - initial_total)
                    print(f"Account {account_id}: Updating current counts - current: {current_total}, initial: {initial_total}, increment: {increment}")
                    
                    await db.execute(
                        "UPDATE accounts SET current_friend_count = ?, current_friend_requests = ?, friend_count = ? WHERE id = ?",
                        (friend_count, friend_requests, increment, account_id)
                    )
            
            await db.commit()

    async def update_band_id(self, account_id: int, band_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE accounts SET band_id = ? WHERE id = ?",
                (band_id, account_id)
            )
            await db.commit()
    
    async def update_band_info(self, account_id: int, band_id: str, band_name: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE accounts SET band_id = ?, band_name = ? WHERE id = ?",
                (band_id, band_name, account_id)
            )
            await db.commit()
    
    async def update_target_and_notes(self, account_id: int, target_friend_count: int, notes: str = None):
        async with aiosqlite.connect(self.db_path) as db:
            print(f"Database update: account_id={account_id}, target={target_friend_count}, notes='{notes}'")
            await db.execute(
                "UPDATE accounts SET target_friend_count = ?, notes = ? WHERE id = ?",
                (target_friend_count, notes, account_id)
            )
            await db.commit()
            
            # 验证更新结果
            cursor = await db.execute(
                "SELECT target_friend_count, notes FROM accounts WHERE id = ?",
                (account_id,)
            )
            row = await cursor.fetchone()
            if row:
                print(f"After update: target={row[0]}, notes='{row[1]}'")
            else:
                print(f"Account {account_id} not found after update")

    async def delete_account(self, account_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            await db.commit()