import urllib.request

req = urllib.request.Request(
    'https://plus.gov.kr/portal/benefitV2/benefitTotalSrvcList/benefitSrvcDtl?svcSeq=809611&bnefType=all&svcId=142100000020',
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
)
try:
    with urllib.request.urlopen(req) as resp:
        print("URL:", resp.url)
        content = resp.read().decode('utf-8')
        print("Content length:", len(content))
        print("Mbuster_T" in resp.url)
except Exception as e:
    print("Error:", e)
