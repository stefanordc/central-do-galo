const fs = require('fs');
const path = './frontend/src/app/noticias/[id]/page.tsx';
let src = fs.readFileSync(path, 'utf8');

if (!src.includes('const showIframe =')) {
    const target = 'const urlValida = noticia.url && (noticia.url.startsWith("http://") || noticia.url.startsWith("https://"));\
  return (';
    
    const replacement = const urlValida = noticia.url && (noticia.url.startsWith("http://") || noticia.url.startsWith("https://"));\
\
  useEffect(() => {\
    if (noticia && noticia.fonte_permite_iframe === null && urlValida) {\
      fetch(\\/api/fontes/\/checar-iframe\, { method: "POST" }).catch(() => {});\
    }\
  }, [noticia, urlValida]);\
\
  const showIframe = urlValida && noticia.fonte_permite_iframe !== false;\
\
  return (
    
    src = src.replace(target, replacement);
    src = src.replace('{urlValida ? (', '{showIframe ? (');
    
    fs.writeFileSync(path, src, 'utf8');
    console.log("Arquivo do frontend atualizado com sucesso!");
}
