import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        # Add user agent to be safe
        page = await b.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        
        print("Visiting list page to get cookies...")
        await page.goto("https://plus.gov.kr/portal/benefitV2/benefitTotalSrvcList", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        
        print("Navigating to detail page...")
        url = "https://plus.gov.kr/portal/benefitV2/benefitTotalSrvcList/benefitSrvcDtl?svcSeq=809611&bnefType=all&svcId=142100000020"
        await page.goto(url, wait_until="networkidle")
        print("URL after navigation:", page.url)
        print("Mbuster_T" in page.url)
        await b.close()

if __name__ == '__main__':
    asyncio.run(run())
