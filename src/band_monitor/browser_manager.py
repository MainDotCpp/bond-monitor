import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from typing import Dict, Optional
import os
from datetime import datetime

class BrowserManager:
    def __init__(self, user_data_dir: str = "browser_sessions"):
        self.user_data_dir = user_data_dir
        self.browsers: Dict[int, Browser] = {}
        self.contexts: Dict[int, BrowserContext] = {}
        self.pages: Dict[int, Page] = {}
        self.monitoring_tasks: Dict[int, asyncio.Task] = {}
        self.playwright = None
        self.previous_counts: Dict[int, dict] = {}  # 存储上一次的计数用于比较
        
        os.makedirs(user_data_dir, exist_ok=True)
        os.makedirs("screenshots", exist_ok=True)

    async def init_playwright(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()

    async def create_browser_session(self, account_id: int) -> Browser:
        await self.init_playwright()
        
        session_dir = os.path.join(self.user_data_dir, f"account_{account_id}")
        os.makedirs(session_dir, exist_ok=True)
        
        browser = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=session_dir,
            headless=False,
            viewport={'width': 1280, 'height': 720},
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-first-run',
                '--disable-default-apps',
                '--disable-features=TranslateUI',
            ],
        )
        
        self.browsers[account_id] = browser
        return browser

    async def get_or_create_page(self, account_id: int) -> Page:
        if account_id not in self.browsers:
            await self.create_browser_session(account_id)
        
        browser = self.browsers[account_id]
        
        if account_id not in self.pages:
            pages = browser.pages
            if pages:
                self.pages[account_id] = pages[0]
            else:
                self.pages[account_id] = await browser.new_page()
        
        return self.pages[account_id]

    async def login_to_band(self, account_id: int, username: str, password: str) -> bool:
        try:
            page = await self.get_or_create_page(account_id)
            
            # 登录流程
            await page.goto('https://auth.band.us/email_login?keep_login=true')
            await page.fill('input[id="input_email"]', username)
            await page.wait_for_timeout(800)
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(800)
            await page.fill('input[id="pw"]', password)
            await page.wait_for_timeout(800)
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(2000)
            
            # 检查是否登录成功 - 等待跳转到band页面或主页
            try:
                await page.wait_for_url('https://www.band.us/**', timeout=3600000)
                return True
            except:
                # 如果没有跳转，检查是否还在登录页面
                if 'auth.band.us' in page.url:
                    print(f"Login failed for account {account_id}: Still on login page")
                    return False
                return True
                
        except Exception as e:
            print(f"Login failed for account {account_id}: {e}")
            return False

    async def try_direct_member_page_access(self, account_id: int, band_id: str) -> bool:
        """
        尝试直接访问Band成员页面（假设用户已登录）
        返回True表示成功访问，False表示需要重新登录
        """
        try:
            page = await self.get_or_create_page(account_id)
            member_url = f"https://band.us/band/{band_id}/member"
            
            print(f"Account {account_id}: Trying direct access to {member_url}")
            await page.goto(member_url, timeout=10000)
            await page.wait_for_timeout(3000)
            
            # 检查是否成功加载成员页面（而不是被重定向到登录页面）
            current_url = page.url
            if '/member' in current_url and band_id in current_url:
                # 进一步检查页面是否包含成员相关内容
                try:
                    # 等待成员页面的关键元素加载
                    await page.wait_for_selector('.bandMemberList, .member-list, [class*="member"]', timeout=5000)
                    print(f"Account {account_id}: Direct access successful - found member content")
                    return True
                except:
                    print(f"Account {account_id}: Direct access failed - no member content found")
                    return False
            else:
                print(f"Account {account_id}: Direct access failed - redirected to {current_url}")
                return False
                
        except Exception as e:
            print(f"Account {account_id}: Direct access exception: {e}")
            return False
    
    async def check_member_page_access(self, account_id: int) -> bool:
        """
        检查当前是否已经在成员页面
        """
        try:
            if account_id not in self.pages:
                return False
                
            page = self.pages[account_id]
            current_url = page.url
            
            # 检查URL是否包含member路径
            if '/member' in current_url:
                # 检查页面是否包含成员内容
                try:
                    await page.wait_for_selector('.bandMemberList, .member-list, [class*="member"]', timeout=2000)
                    return True
                except:
                    return False
            return False
        except:
            return False

    async def navigate_to_band_member_page(self, account_id: int, band_id: str = None) -> str:
        try:
            page = await self.get_or_create_page(account_id)
            
            if band_id:
                # 如果提供了band_id，直接导航到成员页面
                member_url = f"https://band.us/band/{band_id}/member"
                await page.goto(member_url)
                await page.wait_for_timeout(2000)
                return band_id
            else:
                # 等待用户手动导航到band成员页面，或自动检测
                try:
                    await page.wait_for_url('https://www.band.us/band/*/member', timeout=3600000)
                    # 正则提取bandId
                    import re
                    match = re.search(r'https://www\.band\.us/band/(\d+)/member', page.url)
                    if match:
                        extracted_band_id = match.group(1)
                        print(f"Extracted band ID: {extracted_band_id}")
                        return extracted_band_id
                except Exception as e:
                    print(f"Failed to get band ID for account {account_id}: {e}")
                    return None
                    
        except Exception as e:
            print(f"Failed to navigate to band member page for account {account_id}: {e}")
            return None
    
    async def get_current_band_id(self, account_id: int) -> str:
        """从当前页面URL提取Band ID"""
        try:
            page = await self.get_or_create_page(account_id)
            current_url = page.url
            
            # 从URL中提取Band ID
            import re
            match = re.search(r'band\.us/band/(\d+)', current_url)
            if match:
                return match.group(1)
            return None
        except Exception as e:
            print(f"Failed to get current band ID for account {account_id}: {e}")
            return None

    async def capture_screenshot(self, account_id: int, reason: str = "change") -> str:
        """
        捕获页面截图并保存
        返回截图文件路径
        """
        try:
            page = await self.get_or_create_page(account_id)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"account_{account_id}_{reason}_{timestamp}.png"
            filepath = os.path.join("screenshots", filename)
            
            await page.screenshot(path=filepath, full_page=True)
            print(f"Screenshot saved: {filepath}")
            return filepath
        except Exception as e:
            print(f"Failed to capture screenshot for account {account_id}: {e}")
            return None

    async def check_browser_and_page_status(self, account_id: int) -> dict:
        """检查浏览器状态和页面位置"""
        try:
            if account_id not in self.browsers:
                return {'browser_open': False, 'on_member_page': False, 'needs_login': True}
            
            page = await self.get_or_create_page(account_id)
            
            # 检查浏览器是否可访问
            try:
                await page.wait_for_load_state('domcontentloaded', timeout=3000)
                current_url = page.url
                
                # 检查是否在成员页面
                on_member_page = '/member' in current_url and 'band.us/band/' in current_url
                
                return {
                    'browser_open': True,
                    'on_member_page': on_member_page,
                    'needs_login': not on_member_page,
                    'current_url': current_url
                }
            except:
                return {'browser_open': False, 'on_member_page': False, 'needs_login': True}
                
        except Exception as e:
            print(f"Error checking browser status for account {account_id}: {e}")
            return {'browser_open': False, 'on_member_page': False, 'needs_login': True}

    async def get_member_count_and_requests(self, account_id: int, refresh_page: bool = False) -> dict:
        try:
            page = await self.get_or_create_page(account_id)
            
            # 刷新页面（如果需要）
            if refresh_page:
                try:
                    await page.reload()
                    await page.wait_for_load_state('networkidle', timeout=5000)
                except Exception as e:
                    print(f"Failed to refresh page for account {account_id}: {e}")
            
            # 检查浏览器是否已关闭
            try:
                await page.wait_for_load_state('domcontentloaded', timeout=3000)
            except Exception as e:
                print(f"Page not accessible for account {account_id}, browser may be closed: {e}")
                return {'member_count': 0, 'friend_requests': 0, 'browser_closed': True}
            
            result = {
                'member_count': 0,
                'friend_requests': 0,
                'browser_closed': False,
                'band_name': None
            }
            
            # 获取Band名称
            try:
                band_name_element = await page.wait_for_selector('h1.bandName a.uriText', timeout=5000)
                band_name_text = await band_name_element.text_content()
                result['band_name'] = band_name_text.strip() if band_name_text else None
                print(f"Band name: {result['band_name']}")
            except Exception as e:
                print(f"Failed to get band name: {e}")
            
            # 等待并获取成员数量元素
            try:
                member_count_element = await page.wait_for_selector('em[class="count sf_color _memberCount"]')
                member_count_text = await member_count_element.text_content()
                result['member_count'] = int(member_count_text) if member_count_text and member_count_text.isdigit() else 0
                print(f"Member count: {result['member_count']}")
            except Exception as e:
                print(f"Failed to get member count: {e}")
                # 如果无法获取计数，可能需要重新导航
                result['needs_navigation'] = True
            
            # 尝试获取好友请求数量
            try:
                join_status_element = await page.wait_for_selector('a[class="joinStatus"]', timeout=5000)
                if  join_status_element:
                    join_status_text = await join_status_element.text_content()
                    # 正则提取好友请求数量（格式如：pending/123）
                    print(f"Join status text: {join_status_text}")
                    import re
                    match = re.search(r'.*(\d+)$', join_status_text)
                    print(f"Match: {match}")
                    if match:
                        result['friend_requests'] = int(match.group(1)) if match.group(1).isdigit() else 0
                        print(f"Friend requests: {result['friend_requests']}")
            except Exception as e:
                print(f"Failed to get friend requests: {e}")
            
            return result
            
        except Exception as e:
            print(f"Failed to get member count and requests for account {account_id}: {e}")
            return {'member_count': 0, 'friend_requests': 0, 'browser_closed': True}

    async def start_monitoring(self, account_id: int, callback=None):
        if account_id in self.monitoring_tasks:
            self.monitoring_tasks[account_id].cancel()
        
        async def monitor_loop():
            refresh_counter = 0
            while True:
                try:
                    # 每10秒刷新一次页面（每次循环都刷新）
                    refresh_page = True
                    
                    # 获取成员数量和好友请求数量
                    data = await self.get_member_count_and_requests(account_id, refresh_page=refresh_page)
                    
                    if data.get('browser_closed', False):
                        print(f"Browser closed for account {account_id}, stopping monitoring")
                        if callback:
                            await callback(account_id, None, None, datetime.now().isoformat(), browser_closed=True)
                        break
                    
                    # 检查数量是否发生变化
                    current_counts = {
                        'member_count': data['member_count'],
                        'friend_requests': data['friend_requests']
                    }
                    
                    previous_counts = self.previous_counts.get(account_id, {})
                    
                    # 如果是第一次记录或数量发生变化，保存截图
                    if (not previous_counts or 
                        current_counts['member_count'] != previous_counts.get('member_count') or 
                        current_counts['friend_requests'] != previous_counts.get('friend_requests')):
                        
                        # 构建变化描述
                        if previous_counts:
                            member_change = current_counts['member_count'] - previous_counts.get('member_count', 0)
                            request_change = current_counts['friend_requests'] - previous_counts.get('friend_requests', 0)
                            reason = f"member_{member_change:+d}_request_{request_change:+d}"
                            print(f"Account {account_id}: Count changed - Members: {member_change:+d}, Requests: {request_change:+d}")
                        else:
                            reason = "initial"
                            print(f"Account {account_id}: Initial count recorded - Members: {current_counts['member_count']}, Requests: {current_counts['friend_requests']}")
                        
                        # 保存截图
                        screenshot_path = await self.capture_screenshot(account_id, reason)
                        
                        # 更新记录的计数
                        self.previous_counts[account_id] = current_counts.copy()
                    
                    if callback:
                        await callback(
                            account_id, 
                            data['member_count'], 
                            data['friend_requests'],
                            datetime.now().isoformat(),
                            browser_closed=False,
                            band_name=data.get('band_name')
                        )
                    
                    refresh_counter += 1
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"Monitoring error for account {account_id}: {e}")
                    await asyncio.sleep(10)
        
        task = asyncio.create_task(monitor_loop())
        self.monitoring_tasks[account_id] = task

    async def pause_monitoring(self, account_id: int):
        if account_id in self.monitoring_tasks:
            self.monitoring_tasks[account_id].cancel()
            del self.monitoring_tasks[account_id]
        
        # 保留计数记录，暂停时不清理，以便恢复监控时继续比较

    async def close_browser(self, account_id: int):
        if account_id in self.monitoring_tasks:
            self.monitoring_tasks[account_id].cancel()
            del self.monitoring_tasks[account_id]
        
        if account_id in self.pages:
            del self.pages[account_id]
            
        if account_id in self.browsers:
            await self.browsers[account_id].close()
            del self.browsers[account_id]
        
        # 清理计数记录
        if account_id in self.previous_counts:
            del self.previous_counts[account_id]

    async def close_all(self):
        for account_id in list(self.monitoring_tasks.keys()):
            await self.close_browser(account_id)
        
        if self.playwright:
            await self.playwright.stop()