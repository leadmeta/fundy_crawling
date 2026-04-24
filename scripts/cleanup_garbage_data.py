"""
기존 DB에서 쓰레기 데이터를 정리하는 일회성 스크립트.
- 네비게이션/메뉴가 본문에 들어간 레코드의 processed 상태를 SKIPPED로 변경
- 제목이 없거나 본문이 너무 짧은 레코드도 SKIPPED 처리
"""
import sqlite3
import json

DB_PATH = 'data/fundy_records.db'

GARBAGE_MARKERS = [
    'MyGOV', '전체메뉴', '누리집', '로그인 연장하기', '자동 로그아웃',
    '회원가입', '본문 바로가기', '모바일 메뉴 닫기', 'window.__NUXT__',
    '인증서등록/관리', '복합인증관리', '보안센터', '화면크기 제어',
    '시니어 지원', '국민비서 구삐', 'For Foreigners',
]

def is_garbage(text):
    if not text:
        return True
    hit_count = sum(1 for m in GARBAGE_MARKERS if m in text)
    return hit_count >= 3

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 1. 이미 처리된 레코드 중 쓰레기 데이터를 가진 것들을 SKIPPED로 업데이트
cur.execute('''
SELECT p.id, f.title, f.details
FROM processed_funding_records p
JOIN funding_records f ON p.id = f.id
WHERE p.status = 'SUCCESS'
''')
rows = cur.fetchall()

skipped_count = 0
for row in rows:
    rec_id, title, details = row
    title = title or ''
    details = details or ''
    
    should_skip = False
    reason = ''
    
    if not title.strip():
        should_skip = True
        reason = 'empty title'
    elif len(details.strip()) < 30:
        should_skip = True
        reason = f'short details ({len(details)} chars)'
    elif is_garbage(details):
        should_skip = True
        reason = 'garbage content'
    
    if should_skip:
        cur.execute('''
            UPDATE processed_funding_records 
            SET status = 'SKIPPED', extracted_json = NULL 
            WHERE id = ?
        ''', (rec_id,))
        skipped_count += 1
        if skipped_count <= 10:
            print(f'  SKIPPED: {rec_id[:16]}... ({reason}) title={title[:40]}')

conn.commit()
print(f'\nTotal records updated to SKIPPED: {skipped_count}')

# 2. 최종 통계
cur.execute('SELECT status, COUNT(*) FROM processed_funding_records GROUP BY status')
print('\n=== Updated Status Summary ===')
for r in cur.fetchall():
    print(f'  {r[0]}: {r[1]}')

conn.close()
print('\nDone. Now re-run export_processed_to_csv.py to generate clean exports.')
