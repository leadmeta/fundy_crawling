import os
import json
import logging
import sqlite3
import time
from typing import List, Dict, Any, Optional
import requests
import tempfile
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    load_dotenv('.env.local')
except ImportError:
    pass

# For GenAI
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

# For HWP text extraction
try:
    import olefile
except ImportError:
    olefile = None

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class FundingSchema(BaseModel):
    """Target schema for LLM extraction based on Fundy Blueprint (v2.3)"""
    funding_type: str = Field(description="자금 형태 (다음 중 1개 필수: GRANT(무상지원), LOAN(융자), GUARANTEE(보증), SPACE(공간지원), CONTEST(경진대회/행사))", default="GRANT")
    target_types: List[str] = Field(description="지원 대상 분류 (다음 중 1개 이상 필수 배열: INDIVIDUAL(개인/일반인), PRE_FOUNDER(예비창업자), STARTUP(초기/스타트업/창업 7년 이내), CORP(중소/중견/일반기업))")
    
    region: List[str] = Field(description="지원 지역 (예: ['전국'] 또는 ['서울', '경기'] 등 시/도 명칭 단위의 배열)")
    age_requirement: str = Field(description="나이 제한 (예: 만 39세 이하, 제한없음 등)")
    business_years: str = Field(description="업력 요건 (예: 창업 3년 이내, 제한없음 등)")
    revenue_range: str = Field(description="매출 요건 (예: 20억 미만, 제한없음 등)")
    debt_ratio_max: str = Field(description="부채비율 요건 (예: 1000% 이하, 명시안됨 등)")
    
    recruit_start_date: str = Field(description="접수 시작일 (YYYY-MM-DD HH:MM)")
    recruit_end_date: str = Field(description="접수 종료일 (YYYY-MM-DD HH:MM)")
    budget: str = Field(description="기업당 최대 지원 한도 또는 지원 예산")
    apply_method: str = Field(description="신청 방법 (온라인 접수처 등)")
    required_documents: str = Field(description="제출 서류 목록 (핵심 서류 위주로 간결하게)")


class DocumentProcessor:
    """Handles downloading and preparing documents for Gemini."""
    def __init__(self, client):
        self.logger = logging.getLogger("DocumentProcessor")
        self.client = client

    def process_attachments(self, attachment_urls: List[str], attachment_names: List[str]) -> Dict[str, Any]:
        """Downloads files, uploads PDFs to Gemini, and extracts text from HWPs."""
        result = {
            "uploaded_files": [], # List of Gemini File objects
            "hwp_text": ""        # Extracted text from HWPs
        }
        
        for url, name in zip(attachment_urls, attachment_names):
            self.logger.info(f"Processing attachment: {name}")
            try:
                ext = os.path.splitext(name)[1].lower()
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                    response = requests.get(url, timeout=15)
                    response.raise_for_status()
                    tmp_file.write(response.content)
                    tmp_path = tmp_file.name

                if ext == '.pdf':
                    if self.client:
                        self.logger.info(f"Uploading PDF to Gemini: {name}")
                        uploaded_file = self.client.files.upload(file=tmp_path, display_name=name)
                        result["uploaded_files"].append(uploaded_file)
                elif ext == '.hwp':
                    self.logger.info(f"Extracting text from HWP: {name}")
                    result["hwp_text"] += self._extract_hwp(tmp_path) + "\n\n"
                else:
                    self.logger.warning(f"Unsupported extension: {ext}, extracting text if possible")
                    if ext in ['.txt', '.csv']:
                        with open(tmp_path, 'r', encoding='utf-8', errors='ignore') as f:
                            result["hwp_text"] += f.read() + "\n\n"

                os.remove(tmp_path)
            except Exception as e:
                self.logger.error(f"Failed to process {name}: {e}")
                
        return result

    def _extract_hwp(self, file_path: str) -> str:
        text = ""
        if olefile and olefile.isOleFile(file_path):
            try:
                ole = olefile.OleFileIO(file_path)
                if ole.exists('PrvText'):
                    stream = ole.openstream('PrvText')
                    text = stream.read().decode('utf-16le', errors='ignore')
            except Exception as e:
                self.logger.error(f"HWP extraction error: {e}")
        return text

    def cleanup_files(self, uploaded_files: list):
        """Deletes files from Gemini to avoid storage bloat."""
        if not self.client:
            return
        for f in uploaded_files:
            try:
                self.logger.info(f"Deleting temp file from Gemini: {f.name}")
                self.client.files.delete(name=f.name)
            except Exception as e:
                self.logger.error(f"Failed to delete file {f.name}: {e}")


class DataExtractionAgent:
    """Agent responsible for analyzing combined text using LLM."""
    def __init__(self, api_key: str = None):
        self.logger = logging.getLogger("DataExtractionAgent")
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            self.logger.error("GEMINI_API_KEY is not set. Extraction will fail.")
            self.client = None
        else:
            self.client = genai.Client(api_key=key)

    def extract_with_retry(self, prompt: str, files: list, max_retries=3) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None

        contents = [prompt]
        if files:
            contents.extend(files)

        for attempt in range(max_retries):
            try:
                self.logger.info(f"Sending request to Gemini (Attempt {attempt+1}/{max_retries})...")
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=FundingSchema,
                        temperature=0.1
                    ),
                )
                return json.loads(response.text)
            except Exception as e:
                import traceback
                self.logger.error(f"Gemini API Error: {type(e).__name__} - {e}")
                self.logger.debug(traceback.format_exc())
                
                if attempt < max_retries - 1:
                    sleep_time = 2 ** attempt * 5
                    self.logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    self.logger.error("Max retries reached. Extraction failed.")
                    return None

class DBManagerAgent:
    """Agent responsible for reading raw DB and saving processed data."""
    def __init__(self, raw_db_path: str, processed_db_path: str):
        self.raw_db_path = raw_db_path
        self.processed_db_path = processed_db_path
        self.logger = logging.getLogger("DBManagerAgent")
        self._init_processed_table()

    def _init_processed_table(self):
        conn = sqlite3.connect(self.processed_db_path)
        cursor = conn.cursor()
        
        # Check if table exists with old schema and drop if necessary to avoid column errors
        try:
            cursor.execute("SELECT status FROM processed_funding_records LIMIT 1")
        except sqlite3.OperationalError:
            self.logger.info("Migrating old processed_funding_records table schema.")
            cursor.execute("DROP TABLE IF EXISTS processed_funding_records")

        # Add extracted_json column to store the full result
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_funding_records (
                id TEXT PRIMARY KEY,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT,
                extracted_json TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def get_unprocessed_records(self, limit: int = 5) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.raw_db_path)
        cursor = conn.cursor()
        cursor.execute(f"ATTACH DATABASE '{self.processed_db_path}' AS proc_db")
        cursor.execute('''
            SELECT f.id, f.title, f.details, f.attachments, f.attachment_names
            FROM funding_records f
            LEFT JOIN proc_db.processed_funding_records p ON f.id = p.id
            WHERE p.id IS NULL AND f.title IS NOT NULL
            LIMIT ?
        ''', (limit,))
        
        columns = [column[0] for column in cursor.description]
        records = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return records

    def save_processed_record(self, record_id: str, data: Dict[str, Any]):
        # 1. Update basic text columns in raw_db (for backward compatibility if needed)
        try:
            if data:
                conn_raw = sqlite3.connect(self.raw_db_path)
                cursor_raw = conn_raw.cursor()
                try:
                    cursor_raw.execute('''
                        UPDATE funding_records 
                        SET deadline = ?, documents = ?, apply_method = ?
                        WHERE id = ?
                    ''', (
                        data.get('recruit_end_date'),
                        data.get('required_documents'),
                        data.get('apply_method'),
                        record_id
                    ))
                    conn_raw.commit()
                except sqlite3.OperationalError as e:
                    self.logger.warning(f"Could not update original funding_records fields: {e}")
                finally:
                    conn_raw.close()
        except Exception as e:
            self.logger.error(f"Raw DB Update Error for {record_id}: {e}")

        # 2. Save full structured JSON into processed_db
        conn_proc = sqlite3.connect(self.processed_db_path)
        cursor_proc = conn_proc.cursor()
        try:
            status = "SUCCESS" if data else "FAILED"
            json_str = json.dumps(data, ensure_ascii=False) if data else None
            
            cursor_proc.execute('''
                INSERT OR REPLACE INTO processed_funding_records (id, status, extracted_json, processed_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (record_id, status, json_str))
            
            conn_proc.commit()
            self.logger.info(f"Saved processed data for ID: {record_id}")
        except Exception as e:
            self.logger.error(f"Processed DB Save Error for {record_id}: {e}")
            conn_proc.rollback()
        finally:
            conn_proc.close()


class OrchestratorAgent:
    """Main Agent that coordinates the workflow."""
    def __init__(self, raw_db_path: str, processed_db_path: str):
        self.logger = logging.getLogger("OrchestratorAgent")
        self.db_agent = DBManagerAgent(raw_db_path, processed_db_path)
        self.extraction_agent = DataExtractionAgent()
        self.doc_processor = DocumentProcessor(self.extraction_agent.client)

    def run_pipeline(self, limit: int = 5):
        self.logger.info("Starting Data Processing Pipeline...")
        records = self.db_agent.get_unprocessed_records(limit)
        
        if not records:
            self.logger.info("No unprocessed records found.")
            return

        for record in records:
            self.logger.info(f"--- Processing Record: {record['title']} ---")
            
            # 1. Parse Attachments
            attachments = json.loads(record['attachments']) if record['attachments'] else []
            attachment_names = json.loads(record['attachment_names']) if record['attachment_names'] else []
            
            doc_result = self.doc_processor.process_attachments(attachments, attachment_names)
            uploaded_files = doc_result.get("uploaded_files", [])
            hwp_text = doc_result.get("hwp_text", "")
            
            # 2. Extract Data using LLM
            prompt = f"""당신은 정부지원금, 정책자금, 창업지원 사업 공고문을 전문적으로 분석하는 최고 수준의 데이터 추출(Information Extraction) AI입니다.
제공된 공고문의 [제목], [본문] 그리고 [추가 텍스트] 및 첨부된 문서(PDF 등)를 시각적, 맥락적으로 종합 분석하여 주어진 JSON 스키마 형식에 맞게 데이터를 추출해 주세요.

[공고 제목]: {record['title']}

[웹페이지 본문]: 
{record['details']}

[첨부파일 내 추가 텍스트 (HWP 추출본 등)]:
{hwp_text[:5000]}

=== 🚨 Fundy 플랫폼 맞춤형 필수 분석 가이드라인 🚨 ===
1. 교차 검증: 웹페이지 본문과 첨부파일(PDF/HWP)의 내용 중, '첨부파일(PDF)'의 표(Table)와 요강을 최우선으로 신뢰하십시오.
2. 자금 형태 (funding_type): 사업 목적을 분석하여 무상지원금은 GRANT, 대출/융자는 LOAN, 보증은 GUARANTEE, 공간/보육지원은 SPACE, 경진대회/행사는 CONTEST로 정확히 매핑하세요.
3. 지원 대상 (target_types): 자격 요건을 읽고 개인/일반인은 INDIVIDUAL, 사업자가 없는 예비창업자는 PRE_FOUNDER, 창업 7년 이내 스타트업은 STARTUP, 일반 중소/중견기업은 CORP 중 해당하는 코드를 '모두' 배열로 추출하세요.
4. 하드 필터 요건 (Hard Filters): 
   - 지역(region): '전국'인지 특정 '시/도' 단위인지 배열로 추출하세요. (예: ["서울", "경기"])
   - 나이(age_requirement), 업력(business_years), 매출(revenue_range), 부채비율(debt_ratio_max) 등은 숫자가 명확히 명시되어 있다면 정확히 추출하고, 없으면 "제한없음" 또는 "명시안됨"으로 기입하세요.
5. 접수 기간 (recruit_start_date, recruit_end_date): 'YYYY-MM-DD HH:MM' 형태를 철저히 지키세요. (시작일이 없으면 null, 마감일이 명확하지 않으면 null 기입. 억지로 지어내지 말 것)
6. 지원금 (budget): 전체 사업 예산보다 '기업당 최대 지원 한도'를 최우선으로 기입하세요. (예: "기업당 최대 1.5억원")
7. 환각 방지: 명시되지 않은 정보는 절대 유추하지 마세요.
"""
            
            structured_data = None
            if self.extraction_agent.client:
                structured_data = self.extraction_agent.extract_with_retry(prompt, uploaded_files)
            else:
                self.logger.warning("Mocking extraction as Gemini API is not configured.")
                structured_data = {
                    "funding_type": "GRANT",
                    "target_types": ["STARTUP", "PRE_FOUNDER"],
                    "region": ["전국"],
                    "age_requirement": "제한없음",
                    "business_years": "창업 3년 이내",
                    "revenue_range": "제한없음",
                    "debt_ratio_max": "명시안됨",
                    "recruit_start_date": "2026-05-01 09:00",
                    "recruit_end_date": "2026-05-31 18:00",
                    "budget": "최대 1억원",
                    "apply_method": "K-Startup 온라인 접수",
                    "required_documents": "사업계획서"
                }

            # 3. Clean up remote files
            self.doc_processor.cleanup_files(uploaded_files)

            # 4. Save Processed Data
            self.db_agent.save_processed_record(record['id'], structured_data)

if __name__ == "__main__":
    RAW_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "fundy_records_raw.db")
    PROCESSED_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "fundy_records.db")
    
    # Use environment variable or set it directly
    if not os.environ.get("GEMINI_API_KEY"):
        print("WARNING: GEMINI_API_KEY environment variable is not set. Using Mock mode.")
        
    orchestrator = OrchestratorAgent(raw_db_path=RAW_DB_PATH, processed_db_path=PROCESSED_DB_PATH)
    # Process up to 50 records in a batch
    orchestrator.run_pipeline(limit=50)
