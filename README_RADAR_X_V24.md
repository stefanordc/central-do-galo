# Radar do X — v24

Fonte de descoberta: `x.com/<usuario>` via SeleniumBase UC, sem login.

- navegador oculto com `headless2`;
- seletor de post: `article[data-testid="tweet"]`;
- URL canônica: `a[href*="/status/"]`;
- até 3 posts próprios mais recentes por conta;
- renderização final pelo `https://publish.x.com/oembed`;
- cache no Supabase continua usando `posts_x`;
- não resolve CAPTCHA automaticamente.

## Teste

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\backend"
pip install -r requirements.txt
python scripts\diagnosticar_x.py
```
