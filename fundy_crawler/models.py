from sqlalchemy import Column, String, DateTime, Text, create_engine, Integer, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class InstitutionDict(Base):
    __tablename__ = 'institution_dict'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False)

class CategoryDict(Base):
    __tablename__ = 'category_dict'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)

class TargetAudienceDict(Base):
    __tablename__ = 'target_audience_dict'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False)

class IndustryDict(Base):
    __tablename__ = 'industry_dict'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False)

class RegionDict(Base):
    __tablename__ = 'region_dict'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)

class FundingRecord(Base):
    __tablename__ = 'funding_records'

    id = Column(String(64), primary_key=True) # SHA-256 hash of URL + Institution
    site_name = Column(String(200), nullable=False)
    title = Column(String(500), nullable=False, default='')
    date = Column(DateTime)
    institution_id = Column(Integer, ForeignKey('institution_dict.id'))
    operating_agency_id = Column(Integer, ForeignKey('institution_dict.id'))
    recruit_period = Column(String(200)) # Could be non-standard
    deadline = Column(DateTime)
    event_period = Column(String(200))
    category_id = Column(Integer, ForeignKey('category_dict.id'))
    target_audience_id = Column(Integer, ForeignKey('target_audience_dict.id'))
    industry_id = Column(Integer, ForeignKey('industry_dict.id'))
    target_age = Column(String(100)) # 연령조건 (예: 청년 만 39세 이하 등)
    corporate_type = Column(String(100)) # 기업구분 (개인, 법인 등)
    region_id = Column(Integer, ForeignKey('region_dict.id'))
    details = Column(Text)
    benefits = Column(Text)
    evaluation_method = Column(Text)
    startup_history = Column(String(200))
    exclusion_criteria = Column(Text)
    attachments = Column(Text) # JSON string array of links
    attachment_names = Column(Text) # JSON string array of filenames
    apply_method = Column(Text)
    documents = Column(Text)
    contact_agency = Column(String(200))
    contact_phone = Column(String(100))
    contact_email = Column(String(150))
    url = Column(String(500), nullable=False)
    
def db_connect():
    """Performs database connection using database settings from settings.py.
    Returns sqlalchemy engine instance
    """
    return create_engine('sqlite:///data/fundy_records.db')

def create_table(engine):
    Base.metadata.create_all(engine)
