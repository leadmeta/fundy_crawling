import asyncio
from playwright.async_api import async_playwright
import json

async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page()
        
        async def handle_request(route):
            if "benefit" in route.request.url and route.request.method == "POST":
                print(f"POST {route.request.url}")
                print(f"POST DATA: {route.request.post_data}")
            await route.continue_()
            
        await page.route("**/*", handle_request)
        print("Navigating to gov24...")
        await page.goto("https://plus.gov.kr/portal/benefitV2/benefitTotalSrvcList", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        
        print("Clicking '고용·창업' filter...")
        # xpath for the filter can be found in gov24_selector artifact but let's just click by text
        await page.get_by_text("고용·창업").click()
        await page.wait_for_timeout(3000)
        await b.close()

if __name__ == '__main__':
    asyncio.run(run())
