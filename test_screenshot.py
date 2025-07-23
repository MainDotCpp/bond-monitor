#!/usr/bin/env python3
"""
测试截图功能的简单脚本
运行服务器后可以使用此脚本测试截图功能是否正常工作
"""

import asyncio
import sys
import os

# 添加项目路径到sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from band_monitor.browser_manager import BrowserManager

async def test_screenshot():
    """测试截图功能"""
    browser_manager = BrowserManager()
    
    try:
        # 创建一个测试页面
        page = await browser_manager.get_or_create_page(999)  # 使用999作为测试账户ID
        
        # 导航到一个测试页面
        await page.goto('https://www.google.com')
        await page.wait_for_load_state('domcontentloaded')
        
        # 测试截图功能
        print("正在测试截图功能...")
        screenshot_path = await browser_manager.capture_screenshot(999, "test")
        
        if screenshot_path and os.path.exists(screenshot_path):
            print(f"✅ 截图成功保存到: {screenshot_path}")
            print(f"📄 文件大小: {os.path.getsize(screenshot_path)} bytes")
        else:
            print("❌ 截图失败")
            
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
    finally:
        # 清理
        await browser_manager.close_browser(999)
        await browser_manager.close_all()

if __name__ == "__main__":
    print("🧪 开始测试截图功能...")
    asyncio.run(test_screenshot())
    print("🏁 测试完成")