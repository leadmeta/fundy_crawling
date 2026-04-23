import re

detail_regex = r"fn_include_popOpen2\('([^']+)',\s*'[^']+',\s*'([^']+)',\s*'([^']+)'"
detail_template = "https://www.smes.go.kr/main/sportsBsnsPolicy/view?viewPblancSeq={0}&viewCntcInsttCd={1}&viewPblancId={2}"

link = "javascript:fn_include_popOpen2('265081759','0', 'BI16', 'PBLN_000000000120639','Title', 'Detail')"
match = re.search(detail_regex, link)

target_url = detail_template
if match:
    if match.lastindex and match.lastindex >= 1:
        for i in range(1, match.lastindex + 1):
            ext = match.group(i).replace("'", "").replace('"', '').strip()
            target_url = target_url.replace(f"{{{i-1}}}", ext)
    print("MATCH!")
    print(target_url)
else:
    print("NO MATCH")
