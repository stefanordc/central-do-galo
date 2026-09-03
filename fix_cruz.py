import os
def run(filepath):
    if not os.path.exists(filepath): return
    with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
    
    search_str = "return texto.replace(/Atl[eé]tico\\s*-?\\s*MG/gi, 'Atlético');"
    replace_str = "return texto.replace(/Atl[eé]tico\\s*-?\\s*MG/gi, 'Atlético').replace(/\\bcruzeiro\\b/gi, 'Cruzeiro');"
    
    if search_str in content:
        content = content.replace(search_str, replace_str)
        with open(filepath, 'w', encoding='utf-8') as f: f.write(content)
run('frontend/src/app/page.tsx')
run('frontend/src/app/noticias/[id]/page.tsx')
