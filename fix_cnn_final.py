import re, os

def fix(p):
    if not os.path.exists(p): return
    with open(p, 'r', encoding='utf-8') as f:
        c = f.read()
    
    # Ajustando a regra de substituicao da regex JS diretamente no texto
    c = re.sub(r'/Atl\[eé\]tico.*?MG/gi', r'/Atl[eé]tico\\s*-?\\s*MG/gi', c)
    
    # Inserindo metadado
    t = 'const imagem = noticia.imagem_url?.trim() || FALLBACK_IMAGE;'
    h = '''\
  useEffect(() => {\
    if (noticia) {\
      document.title = formatarTituloAtletico(noticia.titulo) + " - Central do Galo";\
    }\
  }, [noticia]);\
'''
    
    if t in c and 'document.title' not in c:
        c = c.replace(t, t + h)
        
    with open(p, 'w', encoding='utf-8') as f:
        f.write(c)

fix('frontend/src/app/page.tsx')
fix('frontend/src/app/noticias/[id]/page.tsx')
