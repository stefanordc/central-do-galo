import re
import os

files = ['frontend/src/app/page.tsx', 'frontend/src/app/noticias/[id]/page.tsx']
for p in files:
    if not os.path.exists(p): continue
    with open(p, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r'function formatarTituloAtletico\(texto: string\): string \{.*?\}'
    new_func = '''function formatarTituloAtletico(texto: string): string {
  if (!texto) return texto;
  return texto.replace(/Atl[eé]tico\\s*-?\\s*MG/gi, 'Atlético').replace(/\\bcruzeiro\\b/gi, 'Cruzeiro');
}'''
    
    content = re.sub(pattern, new_func, content, flags=re.DOTALL)

    with open(p, 'w', encoding='utf-8') as f:
        f.write(content)
