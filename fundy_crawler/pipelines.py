import hashlib
import json
from sqlalchemy.orm import sessionmaker
from scrapy.exceptions import DropItem
from fundy_crawler.models import (
    db_connect, create_table, FundingRecord, 
    InstitutionDict, CategoryDict, TargetAudienceDict, IndustryDict, RegionDict
)
import meilisearch

class NoticeFilterPipeline:
    def __init__(self, exclude_keywords):
        self.exclude_keywords = exclude_keywords

    @classmethod
    def from_crawler(cls, crawler):
        # We can pass global keywords or allow spider configuration
        exclude_keywords = ["결과", "안내", "공지사항", "점검", "발표", "안내문", "재공고 안내"]
        return cls(exclude_keywords)

    def process_item(self, item, spider):
        title = item.get('title', '')
        if any(keyword in title for keyword in self.exclude_keywords):
            # Exception rule: if it looks like a real business despite having "안내"
            if "지원사업" not in title and "모집" not in title and "사업" not in title:
                raise DropItem(f"Title contains excluded word: {title}")
        return item

import os
import tempfile
import requests
import pdfplumber
import docx
import olefile
import zlib
import struct

class AttachmentTextExtractionPipeline:
    def process_item(self, item, spider):
        details = item.get('details', '')
        # 본문 내용이 거의 없는 경우 (50자 이하)
        if len(details.strip()) < 50:
            attachments = item.get('attachments', [])
            if isinstance(attachments, str):
                try:
                    attachments = json.loads(attachments)
                except:
                    attachments = []
            
            extracted_texts = []
            for url in attachments:
                if not url.startswith('http'):
                    continue
                
                # 확장자 판별
                ext = url.split('.')[-1].lower()
                if '?' in ext:
                    ext = ext.split('?')[0]
                
                if ext in ['pdf', 'docx', 'hwp']:
                    try:
                        resp = requests.get(url, timeout=10)
                        if resp.status_code == 200:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                                tmp.write(resp.content)
                                tmp_path = tmp.name
                            
                            text = ""
                            if ext == 'pdf':
                                try:
                                    with pdfplumber.open(tmp_path) as pdf:
                                        for page in pdf.pages[:5]: # 최대 5페이지만 추출 (속도 고려)
                                            text += page.extract_text() + "\n"
                                except Exception as e:
                                    spider.logger.debug(f"PDF Parsing failed: {e}")
                            
                            elif ext == 'docx':
                                try:
                                    doc = docx.Document(tmp_path)
                                    text = "\n".join([p.text for p in doc.paragraphs[:50]]) # 단락 제한
                                except Exception as e:
                                    spider.logger.debug(f"DOCX Parsing failed: {e}")
                                    
                            elif ext == 'hwp':
                                try:
                                    f = olefile.OleFileIO(tmp_path)
                                    dirs = f.listdir()
                                    if ['PrvText'] in dirs:
                                        text = f.openstream('PrvText').read().decode('utf-16le', 'ignore')
                                except Exception as e:
                                    spider.logger.debug(f"HWP Parsing failed: {e}")
                                    
                            os.remove(tmp_path)
                            
                            if text.strip():
                                extracted_texts.append(f"[첨부파일 추출내용]\n{text.strip()}")
                    except Exception as req_err:
                        spider.logger.warning(f"Attachment download failed: {url} - {req_err}")
            
            if extracted_texts:
                new_details = "\n\n".join(extracted_texts)
                item['details'] = details + "\n\n" + new_details
                
        return item

import re

class RegexFallbackExtractionPipeline:
    def process_item(self, item, spider):
        title = item.get('title', '')
        details = item.get('details', '')

        # 1. 접수기간(recruit_period) Fallback
        recruit_period = item.get('recruit_period', '').strip()
        if not recruit_period or recruit_period in ['무관', '없음', '']:
            # 제목 패턴 먼저 확인 (예: 4.13.~4.24.)
            title_date_pattern = r'\((\d{1,2}\.\d{1,2}\.?\s*~?\s*\d{1,2}\.\d{1,2}\.?)\)'
            match = re.search(title_date_pattern, title)
            if match:
                item['recruit_period'] = match.group(1).strip()
            else:
                # 본문 패턴 확인
                match_detail = re.search(r'(?:신청기간|모집기간|접수기간)[\s:;\-\|\[\]]*([0-9\.\s~]+)', details)
                if match_detail:
                    val = match_detail.group(1).strip()
                    if len(val) > 5 and len(val) < 50:
                        item['recruit_period'] = val
                
        # 2. 지원대상(target_audience) Fallback
        target_aud = item.get('target_audience', '').strip()
        if not target_aud or target_aud in ['무관', '없음', '']:
            match_aud = re.search(r'(?:모집대상|지원대상|신청자격|참가대상)[\s:;\-\|\[\]]*([^\n]+)', details)
            if match_aud:
                item['target_audience'] = match_aud.group(1).strip()
        
        # 3. 문의처(contact_agency) Fallback
        contact = item.get('contact_agency', '').strip()
        if not contact or contact in ['무관', '없음', '']:
            match_contact = re.search(r'(?:문의처|문의전화|문의|담당자)[\s:;\-\|\[\]]*([^\n]+)', details)
            if match_contact:
                item['contact_agency'] = match_contact.group(1).strip()
                
        return item


from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def get_canonical_url(url: str) -> str:
    """페이지 번호(cpage) 등 잡다한 쿼리를 날리고 고유 공고번호만 남기는 함수"""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    
    canonical_query = {}
    has_identifier = False
    
    # [기업마당] 고유번호: pblancId
    if 'pblancId' in qs:
        canonical_query['pblancId'] = qs['pblancId'][0]
        has_identifier = True
        
    # [K-Startup 등] 고유번호: pbno
    if 'pbno' in qs:
        canonical_query['pbno'] = qs['pbno'][0]
        has_identifier = True
        
    # [정부24] 등 기타 식별자
    if 'svcSeq' in qs:
        canonical_query['svcSeq'] = qs['svcSeq'][0]
        has_identifier = True
    if 'svcId' in qs:
        canonical_query['svcId'] = qs['svcId'][0]
        has_identifier = True
        
    # 고유번호만 남긴 깔끔한 쿼리 스트링으로 재조립
    if has_identifier:
        new_query = urlencode(canonical_query)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    
    # 알려진 고유 식별자가 없으면 원본 URL을 사용
    return url

class SQLitePipeline:
    def __init__(self):
        engine = db_connect()
        create_table(engine)
        self.Session = sessionmaker(bind=engine)

    def _get_or_create_dict(self, session, dict_class, value):
        if not value: return None
        value = value.strip()
        record = session.query(dict_class).filter_by(name=value).first()
        if not record:
            record = dict_class(name=value)
            session.add(record)
            session.flush() # get ID
        return record.id

    def process_item(self, item, spider):
        session = self.Session()
        
        # 1. Create a unique ID using Canonical URL
        url = item.get('url', '')
        clean_url = get_canonical_url(url)
        hash_id = hashlib.sha256(clean_url.encode('utf-8')).hexdigest()

        # FK Resolution
        institution_id = self._get_or_create_dict(session, InstitutionDict, item.get('institution', ''))
        operating_agency_id = self._get_or_create_dict(session, InstitutionDict, item.get('operating_agency', ''))
        category_id = self._get_or_create_dict(session, CategoryDict, item.get('category', ''))
        target_audience_id = self._get_or_create_dict(session, TargetAudienceDict, item.get('target_audience', ''))
        industry_id = self._get_or_create_dict(session, IndustryDict, item.get('industry', ''))
        region_id = self._get_or_create_dict(session, RegionDict, item.get('region', ''))

        # 2. Check existing record
        exist = session.query(FundingRecord).filter_by(id=hash_id).first()
        
        if exist:
            if not exist.institution_id and not exist.details:
                attachments_str = json.dumps(item.get('attachments', [])) if item.get('attachments') else '[]'
                attachment_names_str = json.dumps(item.get('attachment_names', [])) if item.get('attachment_names') else '[]'
                exist.site_name = item.get('site_name', '') or exist.site_name
                exist.title = item.get('title', '') or exist.title
                exist.date = item.get('date') or exist.date
                exist.institution_id = institution_id
                exist.operating_agency_id = operating_agency_id
                exist.recruit_period = item.get('recruit_period', '')
                exist.deadline = item.get('deadline')
                exist.event_period = item.get('event_period', '')
                exist.category_id = category_id
                exist.target_audience_id = target_audience_id
                exist.industry_id = industry_id
                exist.target_age = item.get('target_age', '')
                exist.corporate_type = item.get('corporate_type', '')
                exist.region_id = region_id
                exist.details = item.get('details', '')
                exist.benefits = item.get('benefits', '')
                exist.evaluation_method = item.get('evaluation_method', '')
                exist.startup_history = item.get('startup_history', '')
                exist.exclusion_criteria = item.get('exclusion_criteria', '')
                exist.attachments = attachments_str
                exist.attachment_names = attachment_names_str
                exist.apply_method = item.get('apply_method', '')
                exist.documents = item.get('documents', '')
                exist.contact_agency = item.get('contact_agency', '')
                exist.contact_phone = item.get('contact_phone', '')
                exist.contact_email = item.get('contact_email', '')
                try:
                    session.commit()
                    spider.logger.info(f"Updated empty record: {url}")
                except:
                    session.rollback()
                finally:
                    session.close()
                item['hash_id'] = hash_id
                return item
            else:
                session.close()
                raise DropItem(f"Duplicate item found: {url}")

        attachments_str = json.dumps(item.get('attachments', [])) if item.get('attachments') else '[]'
        attachment_names_str = json.dumps(item.get('attachment_names', [])) if item.get('attachment_names') else '[]'
        
        record = FundingRecord(
            id=hash_id,
            site_name=item.get('site_name', ''),
            title=item.get('title', ''),
            date=item.get('date'),
            institution_id=institution_id,
            operating_agency_id=operating_agency_id,
            recruit_period=item.get('recruit_period', ''),
            deadline=item.get('deadline'),
            event_period=item.get('event_period', ''),
            category_id=category_id,
            target_audience_id=target_audience_id,
            industry_id=industry_id,
            target_age=item.get('target_age', ''),
            corporate_type=item.get('corporate_type', ''),
            region_id=region_id,
            details=item.get('details', ''),
            benefits=item.get('benefits', ''),
            evaluation_method=item.get('evaluation_method', ''),
            startup_history=item.get('startup_history', ''),
            exclusion_criteria=item.get('exclusion_criteria', ''),
            attachments=attachments_str,
            attachment_names=attachment_names_str,
            apply_method=item.get('apply_method', ''),
            documents=item.get('documents', ''),
            contact_agency=item.get('contact_agency', ''),
            contact_phone=item.get('contact_phone', ''),
            contact_email=item.get('contact_email', ''),
            url=item.get('url', '')
        )
        try:
            session.add(record)
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()

        # Pass item to next pipeline (Meilisearch)
        item['hash_id'] = hash_id 
        return item


class MeilisearchPipeline:
    def __init__(self):
        # Local Meilisearch instance. For now we will just put a try-except layer
        # in case Meilisearch server is not running
        self.client = meilisearch.Client('http://localhost:7700', 'masterKey')
        try:
            self.index = self.client.index('funding_records')
        except:
            self.index = None

    def process_item(self, item, spider):
        if not self.index:
            return item
            
        doc = dict(item)
        doc['id'] = item.get('hash_id')
        if 'hash_id' in doc:
            del doc['hash_id']
            
        try:
            self.index.add_documents([doc])
        except Exception as e:
            spider.logger.error(f"Meilisearch indexing failed: {e}")
            
        return item
