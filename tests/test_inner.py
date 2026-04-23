import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page()
        await page.goto("https://www.smes.go.kr/main/sportsBsnsPolicy", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        html = await page.eval_on_selector('table.tbl-list01', 'el => el.innerHTML')
        with open("log/table_smes.txt", 'w', encoding='utf-8') as f:
            f.write(html)
        await b.close()

if __name__ == '__main__':
    asyncio.run(run())
