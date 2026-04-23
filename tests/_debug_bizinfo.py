"""bizinfo 디버그: Playwright가 실제로 정보를 잘 가져오는지 확인"""
import os, sys, logging
os.environ.setdefault('SCRAPY_SETTINGS_MODULE', 'fundy_crawler.settings')

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from fundy_crawler.spiders.generic_spider import GenericSpider

original_parse_list = GenericSpider.parse_list

def debug_parse_list(self, response):
    print(f"\n[DEBUG] parse_list called for: {response.url}")
    print(f"[DEBUG] Response status: {response.status}")
    print(f"[DEBUG] Response body length: {len(response.text)}")
    
    # Check what is found by CSS selector
    detail_css = self.selectors.get('detail_links_css')
    if detail_css:
        links = response.css(detail_css).getall()
        print(f"[DEBUG] CSS selector: {detail_css}")
        print(f"[DEBUG] Found {len(links)} links via CSS")
        for l in links[:5]:
            print(f"  -> {l}")
            
    # Check what is found by wait_for_selector
    wait_sel = self.selectors.get('wait_for_selector') or self.config.get('wait_for_selector')
    print(f"[DEBUG] wait_for_selector was: {wait_sel}")
    
    print(f"\n[DEBUG] First 2000 chars of body:")
    print(response.text[:2000])
    
    yield from original_parse_list(self, response)

GenericSpider.parse_list = debug_parse_list

settings = get_project_settings()
settings.set('ITEM_PIPELINES', {})
settings.set('CLOSESPIDER_TIMEOUT', 30)
settings.set('LOG_LEVEL', 'DEBUG')
settings.set('DOWNLOAD_DELAY', 1)

process = CrawlerProcess(settings)
process.crawl('generic', target_id='bizinfo')
process.start()
