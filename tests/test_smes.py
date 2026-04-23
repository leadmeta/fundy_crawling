import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating...")
        await page.goto('https://www.smes.go.kr/main/sportsBsnsPolicy', wait_until='networkidle')
        await page.wait_for_timeout(3000)
        links = await page.eval_on_selector_all('table.tbl-list01 a', 'els => els.map(el => el.getAttribute("href"))')
        print(f"Found {len(links)} links:")
        for l in links[:3]: print(l)
        await browser.close()

if __name__ == '__main__':
    asyncio.run(run())
