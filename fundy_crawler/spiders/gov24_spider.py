import scrapy
import json
from scrapy.http import FormRequest

class Gov24Spider(scrapy.Spider):
    name = "gov24"
    
    # 정부24는 API를 직접 호출하여 목록을 가져오고 상세 페이지는 Playwright로 렌더링 후 파싱합니다.
    def start_requests(self):
        url = "https://plus.gov.kr/api/portal/v1.0/api/benefitPlus"
        formdata = {
            "apiDtlUrl": "selectPbnsvcList",
            "pageIndex": "1",
            "srtOdr": "KO"
        }
        yield FormRequest(
            url=url,
            formdata=formdata,
            callback=self.parse_list,
            meta={"pageIndex": 1}
        )

    def parse_list(self, response):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error("Failed to parse JSON")
            return
            
        records = self._find_list_in_json(data)
        
        if not records:
            self.logger.warning("No records found in JSON response")
            
        for item in records:
            svc_id = item.get("svcId", "")
            svc_seq = item.get("svcSeq", "")
            if svc_seq and svc_id:
                # 보조금24 상세 페이지 URL 조합
                detail_url = f"https://plus.gov.kr/portal/benefitV2/benefitTotalSrvcList/benefitSrvcDtl?svcSeq={svc_seq}&bnefType=all&svcId={svc_id}"
                
                # 상세 페이지는 CSR/SPA 렌더링이므로 Playwright를 사용
                yield scrapy.Request(
                    detail_url,
                    callback=self.parse_detail,
                    meta={"playwright": True}
                )
                
        # 최대 50페이지까지 수집 (1페이지 당 기본 10~20건 내외)
        pageIndex = response.meta["pageIndex"]
        if records and pageIndex < 50:
            next_page = pageIndex + 1
            formdata = {
                "apiDtlUrl": "selectPbnsvcList",
                "pageIndex": str(next_page),
                "srtOdr": "KO"
            }
            yield FormRequest(
                url="https://plus.gov.kr/api/portal/v1.0/api/benefitPlus",
                formdata=formdata,
                callback=self.parse_list,
                meta={"pageIndex": next_page}
            )

    def _find_list_in_json(self, data):
        # JSON 트리에서 svcId가 포함된 배열(리스트 오브젝트) 자동 탐색
        if isinstance(data, list):
            for el in data:
                if isinstance(el, dict) and "svcId" in el:
                    return data
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict) and "svcId" in v[0]:
                    return v
                res = self._find_list_in_json(v)
                if res: return res
        return []

    def parse_detail(self, response):
        def extract(xpath):
            text_nodes = response.xpath(xpath).getall()
            return " ".join(t.strip() for t in text_nodes if t.strip())

        institution = extract('//h3[contains(., "접수 및 문의")]/following-sibling::div//h4[contains(., "접수기관")]/following-sibling::ul//text()')
        recruit_period = extract('//h3[contains(., "신청방법")]/following-sibling::div//h4[contains(., "신청기간")]/following-sibling::ul//text()')
        apply_method = extract('//h3[contains(., "서비스 개요")]/following-sibling::div//p[contains(., "신청 방법")]/following-sibling::p//text()')
        contact_agency = extract('//h3[contains(., "접수 및 문의")]/following-sibling::div//h4[contains(., "문의처")]/following-sibling::ul//text()')
        documents = extract('//h3[contains(., "제출 서류")]/following-sibling::div//text()')
        target_audience = extract('//h3[contains(., "서비스 상세")]/following-sibling::div//h4[contains(., "지원대상")]/following-sibling::ul//text()')
        details = extract('//h3[contains(., "서비스 상세")]/following-sibling::div//text()')
        
        # 100세 생신 축하금 같은 제목은 h3.tit-fake 에서 가져올 수 있음
        title = extract('//h3[contains(@class, "tit-fake")]//text()')

        yield {
            'site_name': '정부24(보조금24)',
            'url': response.url,
            'institution': institution if institution else "무관",
            'recruit_period': recruit_period if recruit_period else "무관",
            'deadline': None,  # 추가 파싱 로직 필요할 수 있음
            'apply_method': apply_method if apply_method else "무관",
            'contact_agency': contact_agency if contact_agency else "무관",
            'documents': documents if documents else "무관",
            'target_audience': target_audience if target_audience else "무관",
            'industry': "무관",
            'category': "공공서비스",
            'details': details,
            'attachments': []
        }
