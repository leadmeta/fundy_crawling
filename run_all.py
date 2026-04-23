import os
import sys
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
import yaml

def run_all_crawlers_and_export():
    print("=== [STEP 1] 크롤링 자동화 엔진 시작 ===")
    
    # 1. targets.yaml을 읽어서 어느 스파이더를 돌릴지 결정
    targets_file = "targets.yaml"
    spiders_to_run = []
    
    if os.path.exists(targets_file):
        with open(targets_file, 'r', encoding='utf-8') as f:
            yaml_data = yaml.safe_load(f)
            
            for target in yaml_data.get('targets', []):
                spider_name = target.get('spider')
                target_id = target.get('id')
                if spider_name:
                    spiders_to_run.append({"name": spider_name, "id": target_id})

    if not spiders_to_run:
        print("실행할 스파이더가 없습니다. targets.yaml이나 코드를 확인해주세요.")
        
    print(f"가동 예정 타겟: {[_['id'] for _ in spiders_to_run]}")
    
    # 2. Scrapy 멀티 프로세스 실행기 세팅
    settings = get_project_settings()
    process = CrawlerProcess(settings)
    
    for s in spiders_to_run:
        if s['name'] == 'generic':
            process.crawl('generic', target_id=s['id'])
        else:
            # 기존 레거시 스파이더 지원
            process.crawl(s['name'])
        
    print("크롤링을 시작합니다. 목표: 각 사이트당 최대 5년 or 1000여건 수집 (도달시 Early Stop)")
    
    # 스파이더들을 비동기로 모두 실행하고 완료될 때까지 대기(Blocking)
    process.start()
    
    print("=== [STEP 2] 크롤링 완료, 엑셀(CSV) 변환 시작 ===")
    
    # 3. CSV Export 스크립트 호출 (기존에 만들어둔 파일 활용)
    scripts_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
    if scripts_path not in sys.path:
        sys.path.append(scripts_path)
    from export_to_csv import export_db_to_csv
    export_db_to_csv()
    
    print("=== 모든 자동화 파일 변환 완료 ===")
    
    # 4. 강제 가비지 컬렉션(GC)을 호출하여 보류 상태의 Task 경고(Pending Message)를 미리 모두 뱉어내게 합니다.
    import gc
    import time
    gc.collect()
    time.sleep(0.5) # 경고 메시지가 화면에 출력될 시간 확보
    
    # 5. 마지막 결과 리포트 생성 및 확인 출력
    import generate_report
    generate_report.generate_and_print_report()

    # 6. AI 데이터 전처리 및 정제 (Gemini 멀티모달 파이프라인)
    print("\n=== [STEP 6] AI 데이터 정제 및 분석 시작 ===")
    try:
        import subprocess
        subprocess.run([sys.executable, "data_processor_agent.py"], check=True)
        print("=== AI 데이터 정제 파이프라인 완료 ===")
    except Exception as e:
        print(f"=== AI 데이터 정제 중 오류 발생: {e} ===")


if __name__ == '__main__':
    run_all_crawlers_and_export()
