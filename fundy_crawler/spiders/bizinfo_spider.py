import scrapy
from datetime import datetime, timedelta
from dateutil.parser import parse
from fundy_crawler.items import FundyCrawlerItem

class BizinfoSpider(scrapy.Spider):
    name = "bizinfo"
    # 기업마당 지원사업 공고 리스트 기준 (임시 URL, 실제 구조에 맞게 변경 필요)
    start_urls = ['https://www.bizinfo.go.kr/sii/siia/selectSIIA200View.do']
    
    # 최근 5년 계산 로직
    FIVE_YEARS_AGO = datetime.now() - timedelta(days=5*365)

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={"playwright": True},
                callback=self.parse
            )

    def parse(self, response):
        """지원사업 목록 페이지 파싱"""
        # 공고 리스트 아이템 추출 링크를 가진 a 태그를 직접 찾습니다.
        detail_links = response.css('a[href*="selectSIIA200Detail.do"]::attr(href)').getall()
        
        for link in set(detail_links): # 중복 제거
            self.logger.info(f"선별된 공고 링크: {link}")
            yield response.follow(link, self.parse_item)

        # 3. 다음 페이지 이동 로직 (최대 1000건 혹은 5년 조건 도달 시까지 계속 파싱 자동화)
        # 현재 활성화된 기업마당 페이지네이션을 모방하여 단순 a태그 이동 처리 (추후 XPath 정교화 필요할 수 있음)
        # 1000건 제한 방어 설정 등은 보통 Scrapy Settings(CLOSESPIDER_ITEMCOUNT)로 전역 제어하는게 가장 효과적입니다.
        current_page = response.meta.get('current_page', 1)
        next_page = current_page + 1
        
        # 임시로 최대 100페이지만 보게하여 무한루프 방지 및 1000개 이상 수집 한계 설정
        if current_page < 100:
            next_page_link = f"https://www.bizinfo.go.kr/sii/siia/selectSIIA200View.do?null=&rows=15&cpage={next_page}"
            yield scrapy.Request(
                next_page_link, 
                meta={"playwright": True, "current_page": next_page}, 
                callback=self.parse
            )

    def parse_item(self, response):
        """개별 지원사업 공고 내용 파싱"""
        item = FundyCrawlerItem()
        import re
        
        # 메타데이터 추출
        item['site_name'] = "기업마당(Bizinfo)"
        item['url'] = response.url
        
        def extract_text(keyword):
            # span 태그 중 class가 s_title이고 텍스트에 keyword가 포함된 요소의 다음 div.txt 텍스트 추출
            texts = response.xpath(f'//span[contains(@class, "s_title") and contains(., "{keyword}")]/following-sibling::div[contains(@class, "txt")]//text()').getall()
            return ' '.join(t.strip() for t in texts if t.strip())

        item['institution'] = extract_text("소관부처")
        
        # 날짜 추출 (본문 내 yyyy.mm.dd 패턴 찾기)
        date_match = re.search(r'\b20[12]\d\.\d{2}\.\d{2}\b', response.text)
        if date_match:
            try:
                item['date'] = parse(date_match.group(0).replace('.', '-'))
            except:
                item['date'] = parse(str(datetime.now()))
        else:
            item['date'] = parse(str(datetime.now()))

        # 해시태그 스크립트에서 추출하여 카테고리로 묶음
        tags = re.findall(r"<span>#(.*?)<\/span>", response.text)
        item['category'] = ", ".join(tags) if tags else "해당사항 없음"
        
        # 신규 추가된 필터링 필수 항목 4가지 (기업마당은 기본적으로 본문에 통일된 규격으로 제공하지 않음)
        # 키워드 매칭이나 임시로 무관 처리. 태그에 힌트가 있다면 반영.
        item['target_audience'] = extract_text("지원대상") or "텍스트 본문 참조 (무관)"
        item['industry'] = extract_text("업종") or "무관"
        item['target_age'] = "무관"
        item['corporate_type'] = "무관"
        
        # 상세항목들 추출
        item['recruit_period'] = extract_text("신청기간")
        item['event_period'] = extract_text("사업수행기관")  # 수행기관을 이벤트 기간 위치에 임시 매핑
        details_text = extract_text("사업개요")
        item['details'] = details_text if details_text else ' '.join(response.xpath('//div[contains(@class, "view_cont")]//text()').getall()).strip()
        item['apply_method'] = extract_text("신청 방법")
        item['contact_agency'] = extract_text("문의처")
        item['documents'] = extract_text("제출서류")
        
        # 첨부파일 추출
        attachments = response.css('.attached_file_list a::attr(href)').getall()
        item['attachments'] = [response.urljoin(a) for a in attachments if 'atchFileId' in a]
        
        # 미지원 항목
        item['deadline'] = item['recruit_period']
        item['benefits'] = ""
        item['region'] = item['institution']
        item['contact_phone'] = ""
        item['contact_email'] = ""
        
        yield item
