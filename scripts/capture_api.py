import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        async def extract_request(route):
            request = route.request
            if "benefitPlus" in request.url:
                print(f"API Request URL: {request.url}")
                print(f"API Post Data: {request.post_data}")
            await route.continue_()

        async def extract_response(response):
            if "benefitPlus" in response.url:
                body = await response.text()
                print(f"API Response Body: {body[:500]}")

        await page.route("**/*", extract_request)
        page.on("response", extract_response)

        await page.goto("https://plus.gov.kr/portal/benefitV2/benefitTotalSrvcList", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
