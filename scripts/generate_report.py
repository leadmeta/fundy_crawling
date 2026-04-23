import csv
import atexit
import sys
from collections import defaultdict

def generate_and_print_report():
    print("\n" + "="*50)
    print("=== [결과 보고서] 크롤링 수집 비율 집계 ===")
    print("="*50)
    
    try:
        with open('fundy_exports.csv', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        if not rows:
            print("데이터가 없습니다.")
            return

        # 사이트별 통계
        # stats 구조: stats[site_name] = {'total': 0, 'title': 0, 'details': 0, 'recruit_period': 0, ...}
        stats = defaultdict(lambda: {'total': 0, 'title': 0, 'details': 0, 'recruit_period': 0})
        overall = {'total': 0, 'title': 0, 'details': 0, 'recruit_period': 0}
        
        for r in rows:
            site = r.get('site_name', 'Unknown').strip() or 'Unknown'
            title = r.get('title', '').strip()
            details = r.get('details', '').strip()
            recruit_period = r.get('recruit_period', '').strip()
            
            stats[site]['total'] += 1
            overall['total'] += 1
            
            if title and title.lower() not in ('none', 'nan', 'null'):
                stats[site]['title'] += 1
                overall['title'] += 1
                
            if details and details.lower() not in ('none', 'nan', 'null'):
                stats[site]['details'] += 1
                overall['details'] += 1
                
            if recruit_period and recruit_period.lower() not in ('none', 'nan', 'null'):
                stats[site]['recruit_period'] += 1
                overall['recruit_period'] += 1
                
        # 리포트 내용 구성
        report_content = []
        report_content.append("크롤링 데이터 수집 성공률 요약 보고서\n")
        report_content.append("="*50)
        
        for site, data in stats.items():
            tot = data['total']
            t_cnt = data['title']
            d_cnt = data['details']
            r_cnt = data['recruit_period']
            
            report_content.append(f"사이트명: {site}")
            report_content.append(f" - 전체 수집 건수: {tot}건")
            report_content.append(f" - [제목]     정상수집: {t_cnt}건 ({t_cnt/tot*100:.1f}%)")
            report_content.append(f" - [상세내용] 정상수집: {d_cnt}건 ({d_cnt/tot*100:.1f}%)")
            report_content.append(f" - [접수기간] 정상수집: {r_cnt}건 ({r_cnt/tot*100:.1f}%)")
            report_content.append("-" * 30)

        tot_all = overall['total']
        t_all = overall['title']
        d_all = overall['details']
        r_all = overall['recruit_period']
        
        report_content.append("\n" + "="*50)
        report_content.append("🌟 [전체 통계 요약] 🌟")
        report_content.append(f" - 전체 누적 수집 건수: {tot_all}건")
        report_content.append(f" - [제목]     정상수집 비율: {t_all}건 / {tot_all}건 ({t_all/tot_all*100:.1f}%)")
        report_content.append(f" - [상세내용] 정상수집 비율: {d_all}건 / {tot_all}건 ({d_all/tot_all*100:.1f}%)")
        report_content.append(f" - [접수기간] 정상수집 비율: {r_all}건 / {tot_all}건 ({r_all/tot_all*100:.1f}%)")
        report_content.append("="*50)

        # 화면 출력
        report_text = "\n".join(report_content)
        print(report_text)
        
        # 파일 저장
        with open('log/collection_report.txt', 'w', encoding='utf-8') as f:
            f.write(report_text)
            
        print("\n=> 상세 분석 결과가 'collection_report.txt' 파일로 저장되었습니다.")
        
    except Exception as e:
        print(f"보고서 생성 중 오류 발생: {e}")

def register_report_hook():
    atexit.register(generate_and_print_report)

if __name__ == '__main__':
    generate_and_print_report()
