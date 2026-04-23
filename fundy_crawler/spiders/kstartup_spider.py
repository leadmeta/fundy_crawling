import scrapy
from datetime import datetime, timedelta
from dateutil.parser import parse
from fundy_crawler.items import FundyCrawlerItem

class KstartupSpider(scrapy.Spider):
    name = "kstartup"
    start_urls = ['https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do']

    # K-Startup은 SPA(Single Page App) 형태이거나 Javascript 렌더링이 강제될 확률이 높음
    # Playwright를 활성화합니다.
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_include_page": True
                },
                callback=self.parse
            )
            
    FIVE_YEARS_AGO = datetime.now() - timedelta(days=5*365)

    async def parse(self, response):
        """K-Startup 목록 조회"""
        page = response.meta["playwright_page"]
        
        # 목록 요소 전체 로딩을 대기 (예시 셀렉터)
        # await page.wait_for_selector("div.list_wrap ul li") 
        
        # 실제 환경에서는 li.item 등 리스트의 컨테이너를 가리키게 됨
        items = response.css('ul.biz_list li')
        
        for item_node in items:
            date_str = item_node.css('div.date span::text').get()
            if not date_str:
                continue
                
            try:
                date_obj = parse(date_str)
                if date_obj < self.FIVE_YEARS_AGO:
                    self.logger.info("Reached data older than 5 years. Stopping K-Startup.")
                    await page.close()
                    return
            except ValueError:
                pass
                
            link = item_node.css('a::attr(href)').get()
            if link:
                # K-startup 상세페이지 역시 동적일 수 있으므로 playwright 플래그 추가
                yield response.follow(link, self.parse_item, meta={"playwright": True})

        # Pagination 처리가 필요함
        # K-Startup 페이징은 JS 함수 호출(e.g., fnGoPage(2))일 수 있으므로 
        # Playwright를 통해 클릭 이벤트를 시뮬레이션하거나 Request를 다시 구성해야함.
        await page.close()

    async def parse_item(self, response):
        """본문 상세 내용 추출"""
        item = FundyCrawlerItem()
        item['site_name'] = "K-Startup"
        item['url'] = response.url
        
        # K-Startup 상세페이지 기준 매칭 필터 정보 (가상 셀렉터)
        item['institution'] = response.css('div.info th:contains("전담기관") + td::text').get(default="").strip()
        item['category'] = response.css('div.info th:contains("지원분야") + td::text').get(default="").strip()
        item['target_audience'] = response.css('div.info th:contains("지원대상") + td::text').get(default="").strip()
        item['industry'] = response.css('div.info th:contains("업종") + td::text').get(default="무관").strip()
        item['target_age'] = response.css('div.info th:contains("연령") + td::text').get(default="무관").strip()
        item['corporate_type'] = response.css('div.info th:contains("기업상태") + td::text').get(default="무관").strip()
        
        item['details'] = ' '.join(response.css('div.editor_content_area *::text').getall()).strip()
        
        yield item
