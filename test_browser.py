from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://www.shixiseng.com")
    print("页面标题：", page.title())
    input("按回车关闭浏览器...")
    browser.close()