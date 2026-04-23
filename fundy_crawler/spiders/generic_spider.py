import scrapy
import yaml
import re
import sys
import asyncio
from datetime import datetime, timedelta
from dateutil.parser import parse
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from fundy_crawler.items import FundyCrawlerItem
import os

# Playwright PageMethod: JS 렌더링 완료 대기를 위한 핵심 도구
try:
    from scrapy_playwright.page import PageMethod
except ImportError:
    PageMethod = None

# Windows 환경 asyncio Event Loop 종료 시 RuntimeError 억제
# scrapy_playwright 내부 코루틴이 GC 시점에 정리될 때 _check_closed 에서 발생하는 에러를 원천 차단
_original_check_closed = asyncio.base_events.BaseEventLoop._check_closed
def _patched_check_closed(self):
    try:
        _original_check_closed(self)
    except RuntimeError:
        pass
asyncio.base_events.BaseEventLoop._check_closed = _patched_check_closed

class GenericSpider(scrapy.Spider):
    name = "generic"
    
    # 1년 필터링 제한 (공통)
    ONE_YEAR_AGO = datetime.now() - timedelta(days=365)

    def __init__(self, target_id=None, *args, **kwargs):
        super(GenericSpider, self).__init__(*args, **kwargs)
        self.target_id = target_id
        self.config = self._load_target_config(target_id)
        
        if not self.config:
            raise ValueError(f"Target ID '{target_id}' not found in targets.yaml")
            
        self.start_urls = self.config.get('start_urls', [])
        self.selectors = self.config.get('selectors', {})
        self.requires_playwright = self.config.get('requires_playwright', False)
        
    def _load_target_config(self, target_id):
        # targets.yaml 파일 로드
        yaml_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'targets.yaml')
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            
        for t in data.get('targets', []):
            if t['id'] == target_id:
                return t
        return None

    def _build_playwright_meta(self, extra_meta=None, page_type='list'):
        """Playwright 요청 시 wait_for_selector / wait_time 등을 자동 주입하는 헬퍼.
        
        Args:
            extra_meta: 추가할 meta 딕셔너리
            page_type: 'list'(목록 페이지) 또는 'detail'(상세 페이지)
        """
        meta = {"playwright": self.requires_playwright}
        if extra_meta:
            meta.update(extra_meta)

        if not self.requires_playwright or PageMethod is None:
            return meta

        page_methods = []

        if page_type == 'list':
            # 목록 페이지에서만 wait_for_selector 적용 (상세 페이지는 DOM 구조가 달라 타임아웃 위험)
            wait_sel = self.selectors.get('wait_for_selector') or self.config.get('wait_for_selector')
            if wait_sel:
                page_methods.append(PageMethod("wait_for_selector", wait_sel, timeout=15000))

        # targets.yaml에 wait_time(ms)이 지정된 경우: 고정 대기 시간 부여
        wait_ms = self.selectors.get('wait_time') or self.config.get('wait_time')
        if wait_ms:
            page_methods.append(PageMethod("wait_for_timeout", int(wait_ms)))

        # wait 설정이 없으면 기본 2초 대기 (상세 페이지 JS 렌더링 보장)
        if not page_methods:
            page_methods.append(PageMethod("wait_for_timeout", 2000))

        meta["playwright_page_methods"] = page_methods
        return meta

    async def start(self):
        """Scrapy 2.13+ 비동기 시작점. (레거시 start_requests 대체)"""
        api_config = self.config.get('api_list')
        if api_config:
            yield self._make_api_request(1)
            return

        for url in self.start_urls:
            meta = self._build_playwright_meta({"current_page": 1})
            yield scrapy.Request(
                url,
                meta=meta,
                callback=self.parse_list
            )

    def _make_api_request(self, page_num):
        api_config = self.config.get('api_list')
        url = api_config.get('url')
        method = api_config.get('method', 'GET')
        formdata = api_config.get('formdata', {})
        
        # Replace {page} in formdata string values
        processed_formdata = {}
        for k, v in formdata.items():
            processed_formdata[k] = str(v).format(page=page_num)

        if method.upper() == 'POST':
            if api_config.get('body'):
                # Handle JSON body if specified
                import json
                processed_body_dict = {}
                for k, v in api_config.get('body').items():
                    processed_body_dict[k] = str(v).format(page=page_num, current_page=page_num)
                
                return scrapy.Request(
                    url=url,
                    method='POST',
                    headers=api_config.get('headers', {}),
                    body=json.dumps(processed_body_dict),
                    callback=self.parse_api_list,
                    meta={"playwright": False, "current_page": page_num}
                )
            else:
                return scrapy.FormRequest(
                    url=url,
                    headers=api_config.get('headers', {}),
                    formdata=processed_formdata,
                    callback=self.parse_api_list,
                    meta={"playwright": False, "current_page": page_num}
                )
        else:
            # GET method parameters could be added, but default is standard URL.
            return scrapy.Request(
                url=url,
                headers=api_config.get('headers', {}),
                callback=self.parse_api_list,
                meta={"playwright": False, "current_page": page_num}
            )

    def parse_api_list(self, response):
        import json
        try:
            data = json.loads(response.text)
        except Exception:
            self.logger.error("Failed to parse JSON response in API list")
            return
            
        api_config = self.config.get('api_list')
        template = api_config.get('detail_url_template')
        
        records = self._find_list_in_json(data)
        
        api_detail = self.config.get('api_detail')
        
        for item in records:
            detail_url = template
            if detail_url:
                for k, v in item.items():
                    if f"{{{k}}}" in detail_url:
                        detail_url = detail_url.replace(f"{{{k}}}", str(v))
            
            detail_meta = self._build_playwright_meta({"item_info": item, "detail_page_url": detail_url}, page_type='detail')
            
            if api_detail:
                method = api_detail.get('method', 'GET').upper()
                req_url = api_detail.get('url')
                headers = api_detail.get('headers', {})
                if method == 'POST':
                    formdata = api_detail.get('formdata', {}).copy()
                    processed_formdata = {}
                    for fk, fv in formdata.items():
                        v_str = str(fv)
                        for ik, iv in item.items():
                            if f"{{{ik}}}" in v_str:
                                v_str = v_str.replace(f"{{{ik}}}", str(iv))
                        processed_formdata[fk] = v_str
                    yield scrapy.FormRequest(
                        url=req_url,
                        headers=headers,
                        formdata=processed_formdata,
                        callback=self.parse_api_detail_json,
                        meta=detail_meta,
                        dont_filter=True
                    )
            else:
                yield scrapy.Request(
                    detail_url,
                    callback=self.parse_detail,
                    meta=detail_meta
                )
            
        current_page = response.meta['current_page']
        max_pages = self.selectors.get('max_pages', 50)
        # 만약 배열이 존재하면 다음 페이지 호출 (종료 조건은 API 마다 다를 수 있음)
        if records and current_page < max_pages:
            yield self._make_api_request(current_page + 1)

    def _find_list_in_json(self, data):
        # JSON 트리에서 Object 배열(리스트 오브젝트) 자동 탐색
        if isinstance(data, list):
            for el in data:
                if isinstance(el, dict):
                    return data
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                    return v
                res = self._find_list_in_json(v)
                if res: return res
        return []

    def parse_api_detail_json(self, response):
        import json
        from bs4 import BeautifulSoup
        try:
            data = json.loads(response.text)
        except Exception:
            self.logger.error("Failed to parse detail API JSON")
            return
            
        api_detail = self.config.get('api_detail')
        root_key = api_detail.get('detail_root_json')
        mapping = api_detail.get('mapping', {})
        
        info = response.meta.get('item_info', {})
        
        d_info = data
        if root_key and root_key in data:
            d_info = data[root_key]
            if isinstance(d_info, list) and len(d_info) > 0:
                d_info = d_info[0]
                
        if not isinstance(d_info, dict):
            d_info = {}

        item = FundyCrawlerItem()
        item['site_name'] = self.config.get('name')
        item['url'] = response.meta.get('detail_page_url') or info.get('esiteUrl') or response.url
        
        # 기본 정보 Fallbacks from item_info 
        item['title'] = info.get('svcNm') or info.get('pbnsvcNj') or info.get('title') or ''
        item['recruit_period'] = info.get('reqstTmlmt', '')
        
        for field, key in mapping.items():
            val = d_info.get(key, '')
            if val:
                # 간단한 태그 제거
                soup = BeautifulSoup(str(val), 'lxml')
                item[field] = soup.get_text(separator='\\n').strip()
        
        # Ensure fallback title
        if not item.get('title') and mapping.get('title') in d_info:
            item['title'] = d_info.get(mapping.get('title'), '')
            
        # Ensure details
        if not item.get('details'):
            item['details'] = d_info.get(mapping.get('details', ''), '') or item.get('benefits', '')

        yield item

    def parse_list(self, response):
        """목록 페이지 파싱 (디테일 링크 수집 및 페이지네이션)"""
        # 1. 상세 페이지 링크 추출
        detail_css = self.selectors.get('detail_links_css')
        detail_xpath = self.selectors.get('detail_links_xpath')
        
        detail_links = []
        if detail_css:
            detail_links = response.css(detail_css).getall()
            self.logger.info(f"Extracted {len(detail_links)} detail links using CSS: {detail_css}. First 3: {detail_links[:3]}")
        elif detail_xpath:
            detail_links = response.xpath(detail_xpath).getall()
        else:
            self.logger.error("No detail links selector configured.")
            return

        detail_regex = self.selectors.get('detail_links_regex')
        detail_template = self.selectors.get('detail_url_template')
        
        for link in set(detail_links):
            target_url = link
            if detail_regex and detail_template:
                regex_str = detail_regex
                if regex_str.startswith("r'") and regex_str.endswith("'"):
                    regex_str = regex_str[2:-1]
                elif regex_str.startswith('r"') and regex_str.endswith('"'):
                    regex_str = regex_str[2:-1]
                
                match = re.search(regex_str, link)
                if match:
                    target_url = detail_template
                    if match.lastindex and match.lastindex >= 1:
                        for i in range(1, match.lastindex + 1):
                            ext = match.group(i).replace("'", "").replace('"', '').strip()
                            target_url = target_url.replace(f"{{{i-1}}}", ext)
                    else:
                        ext = match.group(0).replace("'", "").replace('"', '').strip()
                        target_url = target_url.replace("{0}", ext)
                else:
                    continue
                    
            detail_meta = self._build_playwright_meta(page_type='detail')
            # detail_template으로 절대 URL이 만들어진 경우 scrapy.Request 직접 사용
            # (response.follow는 hash fragment를 제거할 수 있어 SPA 사이트에서 실패 가능)
            if target_url.startswith('http'):
                # SPA hash routing: Scrapy의 DUPEFILTER가 #fragment를 무시하므로
                # hash URL은 dont_filter=True로 중복 필터를 건너뜀
                has_hash = '#' in target_url
                yield scrapy.Request(
                    target_url,
                    callback=self.parse_detail,
                    meta=detail_meta,
                    dont_filter=has_hash
                )
            else:
                yield response.follow(
                    target_url, 
                    self.parse_detail,
                    meta=detail_meta
                )

        # 2. 다음 페이지 이동 로직 (Pagination Param 기법)
        current_page = response.meta.get('current_page', 1)
        max_pages = self.selectors.get('max_pages', 100)
        
        if current_page < max_pages:
            next_page = current_page + 1
            pagination_param = self.selectors.get('pagination_param')
            
            if pagination_param:
                # 파라미터를 증가시켜서 요청 생성
                parsed = urlparse(response.url)
                query = parse_qs(parsed.query)
                query[pagination_param] = [str(next_page)]
                new_query = urlencode(query, doseq=True)
                next_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
                
                next_meta = self._build_playwright_meta({"current_page": next_page})
                yield scrapy.Request(
                    next_url,
                    meta=next_meta,
                    callback=self.parse_list
                )

    def extract_field(self, response, field_xpath):
        if not field_xpath:
            return ""
        texts = response.xpath(field_xpath).getall()
        return ' '.join(t.strip() for t in texts if t.strip())

    def parse_detail(self, response):
        """상세 페이지 파싱 (Dynamic Selector 기반)"""
        item = FundyCrawlerItem()
        item['site_name'] = self.config.get('name', 'Unknown')
        item['url'] = response.url
        
        fields_config = self.selectors.get('fields', {})
        
        # 1. 정해진 필드들의 XPath 추출
        for field_name, xpath_val in fields_config.items():
            # item.py 에 선언된 필드와 일치하면 저장
            item[field_name] = self.extract_field(response, xpath_val)
            
        # 2. 본문 내용 공통 추출 로직
        details_xpath = self.selectors.get('details_xpath')
        extracted_details = ""
        if details_xpath:
            extracted_details = self.extract_field(response, details_xpath)
            
        if not extracted_details or len(extracted_details) < 10:
            # Fallback for empty details
            fallback_xpaths = [
                '//div[contains(@class, "view_cont")]//text()',
                '//div[contains(@class, "board_view")]//text()',
                '//div[contains(@class, "txt_area")]//text()',
                '//div[contains(@class, "content")]//text()',
                '//div[@id="contents"]//text()',
                '//div[@id="content"]//text()',
                '//table[contains(@class, "boardview-table")]//text()',
                '//div[contains(@class, "view_top_info")]//text()',
                # 최후의 수단: body 이하의 모든 텍스트
                '//body//text()'
            ]
            for fb in fallback_xpaths:
                text_val = self.extract_field(response, fb)
                # 네비게이션/푸터 등을 감안하여 의미 있는 길이일 때만 채택
                if text_val and len(text_val) > 30:
                    extracted_details = text_val
                    extracted_details = text_val
                    break
                    
        item['details'] = extracted_details.strip() if extracted_details.strip() else '해당사항 없음'
        
        # 3. API 기반 사이트(SPA)에서 상세 페이지 스크래핑 실패 시 item_info에서 폴백
        if 'item_info' in response.meta:
            info = response.meta['item_info']
            if not item.get('title'):
                item['title'] = info.get('svcNm') or info.get('pbnsvcNj') or info.get('title') or ''
            if not item.get('recruit_period') and 'reqstTmlmt' in info:
                item['recruit_period'] = info.get('reqstTmlmt', '')
            if item.get('details') == '해당사항 없음' and 'svcIntrcnCts' in info:
                item['details'] = info.get('svcIntrcnCts', '')
                
        # 3. 첨부파일
        attachments_css = self.selectors.get('attachments_css')
        if attachments_css:
            # ::attr(href) 등 속성 지정자가 있을 경우 제거하여 a 태그 안의 텍스트도 추출할 수 있게 함
            clean_css = attachments_css.split('::attr')[0].strip()
            attachment_links = []
            attachment_names = []
            
            for a_tag in response.css(clean_css):
                href = a_tag.attrib.get('href')
                if not href:
                    href = a_tag.css('::attr(href)').get()
                    
                fname = ''.join(a_tag.css('*::text').getall()).strip()
                if not fname:
                    fname = "첨부파일"
                    
                if href and 'javascript' not in href:
                    attachment_links.append(response.urljoin(href))
                    attachment_names.append(fname)
            item['attachments'] = attachment_links
            item['attachment_names'] = attachment_names
        else:
            item['attachments'] = []
            item['attachment_names'] = []

        # 4. 정규식 추출 (날짜, 카테고리 등 예외 케이스)
        date_regex = self.selectors.get('date_regex')
        if date_regex:
            regex_str = date_regex
            if regex_str.startswith("r'") and regex_str.endswith("'"):
                regex_str = regex_str[2:-1]
            elif regex_str.startswith('r"') and regex_str.endswith('"'):
                regex_str = regex_str[2:-1]
            date_match = re.search(regex_str, response.text)
            if date_match:
                try:
                    item['date'] = parse(date_match.group(0).replace('.', '-'))
                except:
                    item['date'] = parse(str(datetime.now()))
            else:
                item['date'] = parse(str(datetime.now()))
        else:
            # XPath 등에서 미리 date 필드가 들어왔다면 그것을 파싱 시도
            if item.get('date') and isinstance(item['date'], str):
                try:
                    item['date'] = parse(item['date'].replace('.', '-'))
                except:
                    item['date'] = parse(str(datetime.now()))
            else:
                item['date'] = parse(str(datetime.now()))
            
        category_regex = self.selectors.get('category_regex')
        if category_regex:
            tags = re.findall(category_regex.replace("r'", "").replace("'", ""), response.text)
            # category가 이미 xpath로 추출되었다면 추가, 없으면 변경
            if tags:
                ext_cat = ", ".join(tags)
                if item.get('category') and item['category'] != "":
                    item['category'] += f", {ext_cat}"
                else:
                    item['category'] = ext_cat

        # 5. 빈 항목들에 기본값 채우기
        default_fields = ['institution', 'recruit_period', 'event_period', 'category', 'target_audience', 'industry', 'target_age', 'corporate_type', 'region', 'apply_method', 'documents', 'contact_agency', 'contact_phone', 'contact_email']
        for df in default_fields:
            if df not in item or not item[df]:
                item[df] = "무관" if df in ['target_audience', 'industry', 'target_age', 'corporate_type'] else ""
        
        # deadline은 DateTime 필드이므로 빈 문자열 대신 None 유지
        if 'deadline' not in item or not item['deadline']:
            item['deadline'] = None

        # 특수 매핑
        if not item.get('region') and item.get('institution'):
            item['region'] = item['institution']

        # 6. 기간 필터링 (1년)
        if isinstance(item.get('date'), datetime):
            if item['date'] < self.ONE_YEAR_AGO:
                self.logger.info(f"Item too old ({item['date']}): {item.get('title')}")
                return

        yield item
