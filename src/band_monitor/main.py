from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from .models import AccountCreate, MonitorResponse, Account, MonitorStatus
from .database import Database
from .browser_manager import BrowserManager
import os

# Global instances
db = Database()
browser_manager = BrowserManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    yield
    await browser_manager.close_all()

app = FastAPI(title="Band Monitor API", version="1.0.0", lifespan=lifespan)

# Mount static files
static_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# Serve the main page
@app.get("/")
async def read_index():
    static_file = os.path.join(static_path, "index.html")
    if os.path.exists(static_file):
        return FileResponse(static_file)
    return {"message": "Welcome to Band Monitor API", "docs": "/docs"}

# API routes with /api prefix
from fastapi import APIRouter
api_router = APIRouter(prefix="/api")

@api_router.post("/accounts", response_model=MonitorResponse)
async def add_account(account: AccountCreate):
    try:
        account_id = await db.add_account(account.username, account.password)
        return MonitorResponse(
            success=True,
            message="Account added successfully",
            data={"account_id": account_id}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.get("/accounts", response_model=MonitorResponse)
async def get_accounts():
    try:
        accounts = await db.get_all_accounts()
        return MonitorResponse(
            success=True,
            message="Accounts retrieved successfully",
            data={"accounts": [account.model_dump() for account in accounts]}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/accounts/{account_id}", response_model=MonitorResponse)
async def get_account(account_id: int):
    try:
        account = await db.get_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        return MonitorResponse(
            success=True,
            message="Account retrieved successfully",
            data={"account": account.model_dump()}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/accounts/{account_id}/start", response_model=MonitorResponse)
async def start_monitoring(account_id: int):
    try:
        account = await db.get_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # 检查浏览器状态和页面位置
        browser_status = await browser_manager.check_browser_and_page_status(account_id)
        print(f"Browser status for account {account_id}: {browser_status}")
        
        needs_full_setup = False
        
        if browser_status['browser_open'] and browser_status['on_member_page']:
            # 浏览器已打开且在成员页面，尝试直接获取计数
            print(f"Account {account_id}: Browser is open and on member page, testing data retrieval")
            test_data = await browser_manager.get_member_count_and_requests(account_id)
            
            if test_data.get('browser_closed', False) or test_data.get('needs_navigation', False):
                print(f"Account {account_id}: Failed to get data, need full setup")
                needs_full_setup = True
            else:
                print(f"Account {account_id}: Successfully got data, no login needed")
        else:
            print(f"Account {account_id}: Browser not open or not on member page, need full setup")
            needs_full_setup = True
        
        if needs_full_setup:
            # 先尝试直接访问成员页面（如果已有band_id）
            direct_access_success = False
            if account.band_id:
                print(f"Account {account_id}: Attempting direct navigation to band {account.band_id}")
                try:
                    direct_access_success = await browser_manager.try_direct_member_page_access(account_id, account.band_id)
                    if direct_access_success:
                        print(f"Account {account_id}: Direct access successful")
                        needs_full_setup = False  # 直接访问成功，不需要完整设置
                    else:
                        print(f"Account {account_id}: Direct access failed, proceeding with login")
                except Exception as e:
                    print(f"Account {account_id}: Direct access error: {e}, proceeding with login")
            
            # 如果直接访问失败或没有band_id，执行完整登录流程
            if needs_full_setup:
                # 需要重新登录和导航
                login_success = await browser_manager.login_to_band(
                    account_id, account.username, account.password
                )
                
                if not login_success:
                    return MonitorResponse(
                        success=False,
                        message="Login failed"
                    )
                
                # 导航到Band成员页面并获取Band ID
                band_id = await browser_manager.navigate_to_band_member_page(account_id, account.band_id)
                
                # 如果获取到新的band_id，保存到数据库
                if band_id and band_id != account.band_id:
                    await db.update_band_id(account_id, band_id)
        
        # 获取初始计数并保存 (只在账户状态为停止时设置初始值)
        if account.status == MonitorStatus.STOPPED:
            initial_data = await browser_manager.get_member_count_and_requests(account_id)
            if not initial_data.get('browser_closed', False):
                await db.set_initial_counts(
                    account_id, 
                    initial_data['member_count'], 
                    initial_data['friend_requests']
                )
                # 如果获取到Band名称，也保存它
                if initial_data.get('band_name'):
                    current_band_id = account.band_id or (await browser_manager.get_current_band_id(account_id))
                    if current_band_id:
                        await db.update_band_info(account_id, current_band_id, initial_data['band_name'])
        
        async def update_callback(acc_id: int, friend_count: int, friend_requests: int, timestamp: str, browser_closed: bool = False, band_name: str = None):
            if browser_closed:
                # 浏览器被关闭，只更新状态为停止，不重置计数
                await db.update_account_status(acc_id, MonitorStatus.STOPPED)
                print(f"Account {acc_id} monitoring stopped due to browser closure")
            else:
                # 只有在获取到有效数据时才更新计数
                if friend_count is not None and friend_requests is not None:
                    await db.update_current_counts(acc_id, friend_count, friend_requests, timestamp)
                
                # 如果获取到Band名称，也更新它
                if band_name:
                    account = await db.get_account(acc_id)
                    if account and account.band_id:
                        await db.update_band_info(acc_id, account.band_id, band_name)
        
        await browser_manager.start_monitoring(account_id, update_callback)
        await db.update_account_status(account_id, MonitorStatus.RUNNING)
        
        return MonitorResponse(
            success=True,
            message="Monitoring started successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/accounts/{account_id}/pause", response_model=MonitorResponse)
async def pause_monitoring(account_id: int):
    try:
        account = await db.get_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        await browser_manager.pause_monitoring(account_id)
        await db.update_account_status(account_id, MonitorStatus.PAUSED)
        
        return MonitorResponse(
            success=True,
            message="Monitoring paused successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/accounts/{account_id}/resume", response_model=MonitorResponse)
async def resume_monitoring(account_id: int):
    try:
        account = await db.get_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        async def update_callback(acc_id: int, friend_count: int, friend_requests: int, timestamp: str, browser_closed: bool = False, band_name: str = None):
            if browser_closed:
                # 浏览器被关闭，只更新状态为停止，不重置计数
                await db.update_account_status(acc_id, MonitorStatus.STOPPED)
                print(f"Account {acc_id} monitoring stopped due to browser closure")
            else:
                # 只有在获取到有效数据时才更新计数
                if friend_count is not None and friend_requests is not None:
                    await db.update_current_counts(acc_id, friend_count, friend_requests, timestamp)
                
                # 如果获取到Band名称，也更新它
                if band_name:
                    account = await db.get_account(acc_id)
                    if account and account.band_id:
                        await db.update_band_info(acc_id, account.band_id, band_name)
        
        await browser_manager.start_monitoring(account_id, update_callback)
        await db.update_account_status(account_id, MonitorStatus.RUNNING)
        
        return MonitorResponse(
            success=True,
            message="Monitoring resumed successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/accounts/{account_id}", response_model=MonitorResponse)
async def delete_account(account_id: int):
    try:
        account = await db.get_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        await browser_manager.close_browser(account_id)
        await db.delete_account(account_id)
        
        return MonitorResponse(
            success=True,
            message="Account deleted successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/accounts/{account_id}/status", response_model=MonitorResponse)
async def get_account_status(account_id: int):
    try:
        account = await db.get_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # 检查浏览器状态
        browser_status = await browser_manager.check_browser_and_page_status(account_id)
        
        return MonitorResponse(
            success=True,
            message="Account status retrieved successfully",
            data={
                "account": account.model_dump(),
                "browser_status": browser_status
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/accounts/{account_id}/target", response_model=MonitorResponse)
async def update_target(account_id: int, target_data: dict):
    try:
        account = await db.get_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        target_friend_count = target_data.get('target_friend_count', 0)
        notes = target_data.get('notes', None)
        
        print(f"Updating account {account_id}: target={target_friend_count}, notes={notes}")
        await db.update_target_and_notes(account_id, target_friend_count, notes)
        
        return MonitorResponse(
            success=True,
            message="Target and notes updated successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/accounts/{account_id}/close", response_model=MonitorResponse)
async def close_browser(account_id: int):
    try:
        account = await db.get_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # 停止监控并关闭浏览器
        await browser_manager.pause_monitoring(account_id)
        await browser_manager.close_browser(account_id)
        await db.update_account_status(account_id, MonitorStatus.STOPPED)
        
        return MonitorResponse(
            success=True,
            message="Browser closed successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/accounts/{account_id}/screenshot", response_model=MonitorResponse)
async def capture_screenshot(account_id: int):
    try:
        account = await db.get_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # 手动触发截图
        screenshot_path = await browser_manager.capture_screenshot(account_id, "manual")
        
        if screenshot_path:
            return MonitorResponse(
                success=True,
                message="Screenshot captured successfully",
                data={"screenshot_path": screenshot_path}
            )
        else:
            return MonitorResponse(
                success=False,
                message="Failed to capture screenshot"
            )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Include API router
app.include_router(api_router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)