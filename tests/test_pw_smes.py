import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page()
        # list page first to get cookies
        await page.goto("https://www.smes.go.kr/main/sportsBsnsPolicy")
        await page.wait_for_timeout(2000)
        print("Goto detail...")
        await page.goto("https://www.smes.go.kr/main/sportsBsnsPolicy/view?viewPblancSeq=265081472&viewCntcInsttCd=3000&viewPblancId=PBLN_00000000000001", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        html = await page.content()
        with open('log/smes24_detail_pw.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("Done. Length:", len(html))
        await b.close()

if __name__ == '__main__':
    asyncio.run(run())
