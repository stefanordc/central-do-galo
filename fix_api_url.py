import re, os

def fix_url(filepath):
    if not os.path.exists(filepath): return
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Usa regex simples sem complicar aspas
    pattern = r'const API_URL = .*?;'
    new_content = re.sub(pattern, 'const API_URL = "http://localhost:8000";', content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

fix_url('frontend/src/app/page.tsx')
fix_url('frontend/src/app/noticias/[id]/page.tsx')
