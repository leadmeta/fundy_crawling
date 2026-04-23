import re

lines = open('log/run_test_gov24_final_utf8.txt', encoding='utf-8').read()
infos = re.findall(r'이름\s*:\s*(.*)', lines)
print("Names found:", infos)
