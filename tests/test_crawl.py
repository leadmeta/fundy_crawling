r"""
특정 타겟 사이트의 크롤링 테스트 스크립트.
targets.yaml에 등록된 사이트 중 하나를 골라서 5건만 빠르게 수집하고,
결과를 터미널에 보기 좋게 출력합니다.

사용법:
  .\venv\Scripts\python.exe test_crawl.py                # 대화형 메뉴에서 타겟 선택
  .\venv\Scripts\python.exe test_crawl.py bizinfo         # 특정 타겟 ID 직접 지정
  .\venv\Scripts\python.exe test_crawl.py bizinfo --count 10  # 건수 지정 (기본 5건)
"""

import os
import sys
import yaml
import json
import signal
import logging
import warnings
import atexit
from datetime import datetime

# Scrapy/Playwright 관련 경고 사전 억제 (콘솔 출력 클린업)
warnings.filterwarnings('ignore', category=DeprecationWarning, module='scrapy')
warnings.filterwarnings('ignore', message='coroutine.*was never awaited', category=RuntimeWarning)

# scrapy 관련 임포트
os.environ.setdefault('SCRAPY_SETTINGS_MODULE', 'fundy_crawler.settings')

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

# Playwright/asyncio 종료 시 Python GC가 stderr에 직접 쓰는 에러를 억제
# (프로세스 종료 직전에 stderr를 devnull로 교체)
def _suppress_exit_errors():
    sys.stderr = open(os.devnull, 'w')
atexit.register(_suppress_exit_errors)


# ── 수집된 아이템을 메모리에 보관하는 경량 파이프라인 ──
collected_items = []

class TestCollectorPipeline:
    """DB 저장 없이 메모리에만 아이템을 모아두는 테스트용 파이프라인."""

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_item(self, item, spider):
        collected_items.append(dict(item))
        return item


def load_targets():
    """targets.yaml 로드 후 타겟 리스트 반환."""
    yaml_path = os.path.join(os.path.dirname(__file__), 'targets.yaml')
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data.get('targets', [])


def pick_target_interactive(targets):
    """대화형으로 타겟을 고르게 합니다."""
    print("\n" + "=" * 60)
    print("  등록된 크롤링 타겟 목록")
    print("=" * 60)
    for i, t in enumerate(targets, 1):
        pw = "Playwright" if t.get('requires_playwright') else "Static"
        print(f"  {i:>3}. [{t['id']:<20}] {t['name']:<25} ({pw})")
    print("=" * 60)

    while True:
        choice = input("\n테스트할 타겟 번호 또는 ID를 입력하세요 (q=종료): ").strip()
        if choice.lower() == 'q':
            sys.exit(0)
        # 번호로 선택
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(targets):
                return targets[idx]
            print("  범위를 벗어났습니다. 다시 입력해 주세요.")
        else:
            # ID로 선택
            for t in targets:
                if t['id'] == choice:
                    return t
            print(f"  '{choice}' ID를 찾을 수 없습니다. 다시 입력해 주세요.")


def pretty_print_results(target, items, max_detail_len=200):
    """수집된 아이템들을 보기 좋게 터미널에 출력합니다."""
    print("\n")
    print("=" * 70)
    print(f"  테스트 결과: {target['name']} ({target['id']})")
    print(f"  수집 건수: {len(items)}건")
    print("=" * 70)

    if not items:
        print("\n  수집된 데이터가 0건입니다!")
        print("  가능한 원인:")
        print("    1. selectors.detail_links_css 또는 detail_links_xpath 가 실제 HTML과 맞지 않음")
        print("    2. 사이트가 Playwright(JS 렌더링)를 필요로 하는데 requires_playwright: false로 설정됨")
        print("    3. 사이트가 접속을 차단하거나 robots.txt로 막고 있음")
        print("    4. start_urls 주소가 잘못됨")
        return

    import json
    import os

    # 전체 데이터 JSON 파일로 덤프
    os.makedirs('log', exist_ok=True)
    with open('log/test_crawl_result.json', 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2, default=str)
    print("\n  => 전체 데이터 세부 결과가 'log/test_crawl_result.json' 파일로 저장되었습니다!\n")

    for idx, item in enumerate(items, 1):
        print(f"\n{'-' * 70}")
        print(f"  [{idx}/{len(items)}]")
        print(f"{'-' * 70}")

        # 모든 필드를 순회하며 출력 (details, attachments는 제외하거나 별도 처리)
        for key, val in item.items():
            if key in ('details', 'attachments') or not val or val == '무관':
                continue
                
            val_clean = ' '.join(str(val).split())
            if len(val_clean) > 80:
                val_clean = val_clean[:77] + "..."
            try:
                print(f"  {key:<15}: {val_clean}")
            except UnicodeEncodeError:
                print(f"  {key:<15}: {val_clean.encode('cp949', errors='replace').decode('cp949')}")

        # 본문(details)은 미리보기만
        details = item.get('details', '')
        if details:
            details_clean = ' '.join(str(details).split())
            preview = details_clean[:max_detail_len]
            if len(details_clean) > max_detail_len:
                preview += "..."
            try:
                print(f"  {'details_preview':15}: {preview}")
            except UnicodeEncodeError:
                print(f"  {'details_preview':15}: {preview.encode('cp949', errors='replace').decode('cp949')}")

        # 첨부파일
        att = item.get('attachments', [])
        if att and att != '[]':
            if isinstance(att, str):
                try: att = json.loads(att)
                except: pass
            if att and isinstance(att, list):
                print(f"  {'attachments':15}: {len(att)}건")
                for a in att:
                    print(f"      - {a}")

    # 데이터 품질 요약
    print(f"\n{'=' * 70}")
    print("  데이터 품질 요약")
    print(f"{'=' * 70}")
    
    quality_fields = ['title', 'institution', 'recruit_period', 'category', 'details', 'target_audience', 'contact_agency']
    for field in quality_fields:
        filled = sum(1 for it in items if it.get(field) and it[field] not in ('', '무관'))
        rate = (filled / len(items)) * 100
        bar = "#" * int(rate // 5) + "-" * (20 - int(rate // 5))
        label_map = {
            'title': '제목',
            'institution': '기관명',
            'recruit_period': '접수기간',
            'category': '카테고리',
            'details': '본문내용',
            'target_audience': '지원대상',
            'contact_agency': '문의처',
        }
        print(f"  {label_map.get(field, field):<10}: {bar} {rate:5.1f}% ({filled}/{len(items)})")
    
    print(f"{'=' * 70}")
    print(f"  테스트 완료 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print()


def main():
    targets = load_targets()
    
    if not targets:
        print("targets.yaml에 등록된 타겟이 없습니다.")
        sys.exit(1)

    # 커맨드라인 인자 파싱
    target_id = None
    test_count = 5
    
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--count' and i + 1 < len(args):
            test_count = int(args[i + 1])
            i += 2
        elif not args[i].startswith('-'):
            target_id = args[i]
            i += 1
        else:
            i += 1

    # 타겟 선택
    if target_id:
        target = None
        for t in targets:
            if t['id'] == target_id:
                target = t
                break
        if not target:
            print(f"'{target_id}' ID가 targets.yaml에 없습니다.")
            sys.exit(1)
    else:
        target = pick_target_interactive(targets)

    print(f"\n[{target['name']}] 테스트 크롤링 시작 (최대 {test_count}건)...")
    print(f"   URL: {target.get('start_urls', ['?'])[0]}")
    print(f"   Playwright: {'Yes' if target.get('requires_playwright') else 'No'}")
    print()

    # Scrapy 설정 오버라이드: DB 파이프라인 OFF, 테스트 파이프라인과 추가 텍스트 추출 파이프라인은 켜기
    settings = get_project_settings()
    settings.set('ITEM_PIPELINES', {
        'fundy_crawler.pipelines.NoticeFilterPipeline': 200,
        'fundy_crawler.pipelines.AttachmentTextExtractionPipeline': 250,
        'fundy_crawler.pipelines.RegexFallbackExtractionPipeline': 270,
        '__main__.TestCollectorPipeline': 300,
    })
    settings.set('CLOSESPIDER_ITEMCOUNT', test_count)
    settings.set('CLOSESPIDER_TIMEOUT', 120)   # 테스트니까 2분 타임아웃
    settings.set('LOG_LEVEL', 'ERROR')          # 경고/로그 최소화
    settings.set('DOWNLOAD_DELAY', 1.0)

    # asyncio/Scrapy 경고 로그 억제
    logging.getLogger('asyncio').setLevel(logging.CRITICAL)
    logging.getLogger('py.warnings').setLevel(logging.CRITICAL)

    process = CrawlerProcess(settings)
    spider_name = target.get('spider', 'generic')
    
    if spider_name == 'generic':
        process.crawl('generic', target_id=target['id'])
    else:
        process.crawl(spider_name)

    process.start()

    # 결과 출력
    pretty_print_results(target, collected_items[:test_count])


if __name__ == '__main__':
    main()
