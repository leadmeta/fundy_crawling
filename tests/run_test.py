import logging
from scrapy.cmdline import execute

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        execute([
            'scrapy', 'parse', 
            '-c', 'parse_list', 
            '-d', '2', 
            'https://plus.gov.kr/api/portal/v1.0/api/benefitPlus', 
            '--spider=generic', 
            '-a', 'target_id=gov24'
        ])
    except SystemExit:
        pass
