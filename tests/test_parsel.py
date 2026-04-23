import asyncio
from playwright.async_api import async_playwright
from scrapy import Selector

async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page()
        print("Navigating...")
        await page.goto("https://www.smes.go.kr/main/sportsBsnsPolicy", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        html = await page.content()
        sel = Selector(text=html)
        css_val = sel.css('table.tbl-list01 td.gonggoNm a::attr(href)').getall()
        print("Links found by parsel:", len(css_val))
        print(css_val[:2])
        await b.close()

if __name__ == '__main__':
    asyncio.run(run())
