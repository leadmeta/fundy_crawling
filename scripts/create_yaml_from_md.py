import re
import yaml
import os

with open("SiteList.md", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_targets = []
for line in lines:
    line = line.strip()
    if not line: continue
    if line.startswith("[OK]"): continue
    
    # parse "Site Name: https://..." or "Site Name (Abbr): https://..."
    match = re.search(r'^([^:]+):\s*(https?://\S+)', line)
    if match:
        name = match.group(1).strip()
        url = match.group(2).strip()
        
        # generate ID from URL domain
        from urllib.parse import urlparse
        domain_parts = urlparse(url).netloc.split('.')
        # usually 2nd to last or 3rd to last is the id
        if domain_parts[0] == 'www':
            id_str = domain_parts[1]
        else:
            id_str = domain_parts[0]
            
        target = f"{id_str}"
        new_targets.append((name, url, target))

yaml_text = ""
for name, url, target in new_targets:
    yaml_text += f"""
  - id: "{target}"
    name: "{name}"
    type: "portal"
    start_urls: 
      - "{url}"
    spider: "generic"
    requires_playwright: true
    selectors:
      # TODO: DOM 분석 및 갱신 필요
      detail_links_xpath: ''
      pagination_param: ''
      max_pages: 1
      fields:
        title: ''
        institution: ''
        operating_agency: ''
        recruit_period: ''
        event_period: ''
        category: ''
        region: ''
        benefits: ''
        apply_method: ''
        contact_agency: ''
        contact_phone: ''
        contact_email: ''
        documents: ''
        target_audience: ''
        target_age: ''
        startup_history: ''
        exclusion_criteria: ''
        evaluation_method: ''
        industry: ''
      details_xpath: ''
      attachments_css: ''
"""

with open("targets.yaml", "a", encoding="utf-8") as f:
    f.write(yaml_text)

print(f"Added {len(new_targets)} sites to targets.yaml")
