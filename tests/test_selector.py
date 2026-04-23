from scrapy import Selector

html = '''
<table class="tbl-list01">
    <tr>
        <td class="gonggoNm">
            <a href="javascript:fn_include_popOpen2('265081759','0', 'BI16', 'PBLN_000000000120639','Title', 'Detail')">Link</a>
        </td>
    </tr>
</table>
'''

sel = Selector(text=html)
links = sel.css('table.tbl-list01 td.gonggoNm a::attr(href)').getall()
print("Links:", links)
