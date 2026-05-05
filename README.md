# Startup Policy Funding Crawler

창업 관련 정책 자금 모집 공고(최근 5년 데이터)를 주기적으로 수집하고 중복 없이 저장하기 위해 제작된 Scrapy & Playwright 기반 크롤링 시스템입니다.
본 엔진은 **SaaS(서비스형 소프트웨어) 연동**을 철저히 고려하여 구축되었으며, 로컬 파일이 아닌 SQLite DB에 데이터를 1차 안전 보관 후 추출하는 방식을 사용합니다.




## 1. 실행 방법
터미널(파워쉘 혹은 CMD)을 열고 프로젝트 최상단 경로(`d:\Project\20260406_clawling_python_fundy`)에서 다음 명령어 하나만 입력하면 끝납니다.

```bash
# 가상환경의 파이썬으로 전체 크롤러 및 추출기 자동 실행
.\venv\Scripts\python.exe run_all.py
```
위 명령어를 실행하면:
1. `targets.yaml`에 등록된 50개 사이트의 룰셋을 스파이더가 읽어들입니다.
2. 각 사이트를 돌며 중복되지 않은 새로운 공고만 찾아 `data/fundy_records.db` 에 즉시 영구 저장합니다.
3. 모든 크롤링이 끝나면 DB 내용을 최신순 정렬하여 `fundy_exports.csv` 에 덮어쓰기 형태로 추출합니다.
4. 사이트별 데이터품질 수집률(제목, 내용 등 정상 수집 비율)을 집계한 요약 리포트가 화면에 출력되며, 파일(`collection_report.txt`)로도 자동 파일 생성됩니다.
5. **AI 데이터 정제 및 분석 (신규/비동기)**: 크롤링된 공고 본문과 첨부파일(PDF, HWP 등)을 **Gemini 2.5 Flash** 멀티모달 AI를 사용해 종합 분석하고, 서비스에 맞게 정형화된 JSON 데이터를 추출하여 데이터베이스(`processed_funding_records` 테이블)에 최종 저장합니다. (`asyncio` 병렬 처리 도입으로 50개 데이터를 단 몇 초~수십 초 이내에 초고속으로 정제합니다!)



> **작업을 중간에 중지했을 때는?**
> 크롤링은 중지되더라도 그때까지 수집된 데이터는 DB에 안전하게 보관되어 있습니다. 단지 마지막 과정인 '엑셀 내보내기'가 안된 상태이므로, 이 때는 아래 명령어로 수동 내보내기를 진행하시면 됩니다.
> `.\venv\Scripts\python.exe export_to_csv.py`







### 개별 사이트 테스트 (크롤링이 잘 되는지 5건만 확인)
새로운 사이트를 `targets.yaml`에 추가한 뒤, 전체 크롤링 전에 **해당 사이트만 골라서 5건만 빠르게 테스트**할 수 있습니다.
DB에는 저장되지 않고 터미널 화면에만 결과가 출력되므로 안심하고 반복 실행 가능합니다.

```bash
# 대화형 메뉴에서 타겟 선택
.\venv\Scripts\python.exe test_crawl.py

# 특정 타겟 ID 직접 지정
.\venv\Scripts\python.exe test_crawl.py bizinfo

# 수집 건수 변경 (기본 5건)
.\venv\Scripts\python.exe test_crawl.py bizinfo --count 10
```
실행이 끝나면 각 항목의 기관명, 접수기간, 본문 미리보기 등과 함께 **데이터 품질 요약(채워진 비율 막대 그래프)**이 터미널에 표시됩니다.




## 2. 데이터 구조 및 활용 (SaaS 관점)
- 크롤링 하는 즉시 `data/fundy_records.db` (SQLite 로컬 데이터베이스)에 데이터가 기록 및 업데이트 됩니다.
- 해시(`hash_id`)를 기반으로 공고가 완전히 똑같으면 중복 저장(업데이트)을 방지하므로, 동일한 명령을 매일 실행해도 데이터가 꼬이지 않습니다.
- **SaaS 서비스 시:** 차후 이 SQLite DB를 그대로 PostgreSQL이나 Supabase 클라우드로 이관만 하면 곧바로 실시간 웹서비스용 데이터베이스로 작동할 수 있도록 구조화되어 있습니다. 기존의 엑셀(`.xlsx`) 방식보다 10배 이상 안정적입니다.
- 스크립트 실행 시 `.csv` 파일은 항상 전체 DB 리스트를 기준으로 **새롭게 덮어쓰기** 됩니다 (항상 최신본으로 유지됨).







## 3. GitHub Actions 배포 및 자동화 (CI/CD)
이 크롤러 프로젝트(`fundy_crawling`)는 GitHub Actions를 통해 서버 없이 정기적으로 자동 실행되도록 설계되어 있습니다. 
저장소가 Public이더라도 프로젝트에 포함된 `.gitignore` 설정 덕분에 로컬의 `.env.local` 파일은 업로드되지 않아 안전합니다.

**필수 설정 (GitHub Secrets)**
현재 크롤링 및 AI 정제 코드에서 **실제로 요구하는 환경 변수는 단 1개**입니다.
GitHub 저장소의 **[Settings] -> [Secrets and variables] -> [Actions]** 메뉴에 다음 값을 직접 등록해 주세요.
*   **Name**: `GEMINI_API_KEY`
*   **Secret**: `AIzaSy...` (발급받은 실제 키 값)

> **참고:** 로컬 `.env.local` 파일에 들어있는 다른 서비스 키(Supabase, OpenAI, Cloudflare R2 등)는 메인 웹 서비스용이므로, 현재 이 독립적인 크롤러의 GitHub Secrets에는 굳이 등록하실 필요가 없습니다.


## 4. 새로운 사이트 추가 (YAML 동적 규칙 추가법)
파이썬 코드를 짤 필요 없이 **`targets.yaml`** 파일에 사이트와 HTML 경로(CSS/XPath)만 추가해주면 범용(Generic) 크롤러 엔진이 자동으로 인식하여 사이트를 수집합니다. HTML 태그 맵핑을 직접 하시기 어렵다면, **AI(Antigravity)에게 URL을 주면서 알아서 분석해 달라고 요청하시는 것이 가장 빠르고 확실한 방법입니다!**


### 자동 방법 : AI에게 구조 분석 요청하기 (추천)
HTML 요소 검사(F12)나 XPath 작성법을 모르시더라도 아래와 같은 양식으로 AI에게 채팅을 보내시면, AI가 사이트에 직접 접속하여 폼 구조를 뜯어보고 `targets.yaml`에 알맞은 규칙을 완벽하게 작성해 줍니다. 
복지로: https://www.bokjiro.go.kr - 보건복지 분야 지원금 및 사회복지 서비스.

**[AI에게 보내는 질문/명령 예시 양식]**
> "새로운 크롤링 사이트를 추가하고 싶어.
> 타겟 이름: 복지로
> id: 'bokjiro'
> URL: https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52005M.do
> 이 URL과 상세 페이지의 HTML 구조(DOM)를 네가 직접 분석해서, 제목, 사이트명, 등록날짜, 주관기관, 사업수행기관, 모집(접수)기간, 사업(행사)기간, 카테고리(정책 종류), 지역, 상세내용, 혜택, 첨부파일들의 모든 링크, 신청방법, 제출서류, 문의기관, 문의 연락처, 문의 이메일, 공고 링크, 평가방법, 대상연령, 대상, 창업업력, 제외대상, 첨부파일명그외 항목들의 XPath/CSS Selector 규칙을 뽑아내줘. 그리고 그 결과를 내 targets.yaml 파일에 설정한 id로 바로 추가 업데이트 해줘."



AI는 자체 내장 브라우저 역량(`gstack-main / Browser Subagent`)을 가지고 있으므로, URL만 주시면 사이트를 스캔하여 양식에 맞는 데이터를 바로 채워넣습니다!

---

### 수동 방법 : 직접 분석 및 추가 (고급 현업자용)
1. `targets.yaml` 파일을 엽니다.
2. 브라우저에서 크롤링할 사이트를 열고 개발자 도구(F12)를 켜서 원하는 데이터 위치한 `<tag>`의 XPath나 CSS 속성을 복사합니다.
3. 아래 템플릿 구조를 `targets.yaml` 가장 아래에 붙여넣고 셀렉터 속성을 교체합니다.

```yaml
  - id: "new_site_id"
    name: "새로운 지원센터 이름"
    type: "agency"
    start_urls: 
      - "https://www.새로운웹사이트주소.com/notice_list"
    spider: "generic"
    requires_playwright: false
    selectors:
      detail_links_css: 'tbody tr td.title a::attr(href)' # 상세 페이지로 가는 a태그 링크 규칙
      pagination_param: "page" # 다음페이지로 넘기는 파라미터 
      fields:
        institution: '//th[contains(., "기관")]/following-sibling::td//text()' # 기관명 위치
        recruit_period: '//th[contains(., "접수기간")]/following-sibling::td//text()'
      details_xpath: '//div[@class="content_body"]//text()' # 본문 전체 내용 위치
```
크롤러는 추가된 규칙을 매 실행 시 자동으로 감지하여 작동합니다.
