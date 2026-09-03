import os, re

home_path = 'frontend/src/app/page.tsx'
noticia_path = 'frontend/src/app/noticias/[id]/page.tsx'

home_api = None
if os.path.exists(home_path):
    with open(home_path, 'r', encoding='utf-8') as f:
        for line in f:
            if 'const API_URL' in line:
                home_api = line.strip()
                break

if os.path.exists(noticia_path) and home_api:
    with open(noticia_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = re.sub(r'const API_URL = .*?;', home_api, content)
    
    with open(noticia_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
