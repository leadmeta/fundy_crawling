import urllib.request
import urllib.parse
import json

data = {
    'apiDtlUrl': 'selectPbnsvcList',
    'srchwrd': '',
    'sggNm': '',
    'svcFdCd': 'NB0304',
    'sittnCd': '',
    'pageIndex': '1',
    'srtOdr': 'KO'
}
data_enc = urllib.parse.urlencode(data).encode('utf-8')

req = urllib.request.Request(
    'https://plus.gov.kr/api/portal/v1.0/api/benefitPlus', 
    method='POST', 
    headers={
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://plus.gov.kr/portal/benefitV2/benefitTotalSrvcList',
        'Origin': 'https://plus.gov.kr',
        'X-Requested-With': 'XMLHttpRequest'
    }, 
    data=data_enc
)
try:
    r = urllib.request.urlopen(req)
    response_text = r.read().decode('utf-8')
    js = json.loads(response_text)
    with open('log/gov24_resp.txt', 'w', encoding='utf-8') as f:
        f.write(response_text)
except Exception as e:
    print(e)
