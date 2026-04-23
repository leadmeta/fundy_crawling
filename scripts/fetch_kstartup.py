import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # 목록 페이지 접속
        await page.goto("https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        
        # HTML 덤프
        list_html = await page.content()
        with open("log/kstartup_list.html", "w", encoding="utf-8") as f:
            f.write(list_html)

        # 첫 번째 항목 클래스나 링크 찾기
        links = await page.eval_on_selector_all("ul.board_list a, a.btn_detail, .list_tr a, ul.biz_list a", "elements => elements.map(e => e.href || e.onclick?.toString() || e.outerHTML)")
        print(f"List Links: {links[:3]}")
        
        # 클릭할 수 있는 요소 찾아 누르기, 또는 직접 이동해보기
        # K-Startup은 보통 javascript:fn_goDetail(...) 또는 href 속성
        try:
            # try clicking first typical link
            elements = await page.query_selector_all("ul.board_list a")
            if not elements:
                elements = await page.query_selector_all("ul.biz_list a")
            if elements:
                await elements[0].click()
                await page.wait_for_timeout(4000)
                detail_html = await page.content()
                with open("log/kstartup_detail.html", "w", encoding="utf-8") as f:
                    f.write(detail_html)
                print(f"Detail page captured: {page.url}")
        except Exception as e:
            print(f"Could not click and fetch detail: {e}")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
