# Radar do X — v25

Fonte mantida: `x_seleniumbase_uc_scrape`.

## Correções

- Mantém SeleniumBase UC sem login e headless por padrão.
- Usa `page_load_strategy=eager` para evitar ficar preso no carregamento contínuo do X.
- Em headless, usa `driver.get()` com o driver UC já patchado; `uc_open_with_reconnect()` fica apenas para execução headed.
- Usa um perfil guest criado pelo próprio UC (`.x_public_uc_profile`) e ignora automaticamente o antigo `.x_chrome_profile` usado pelas versões com login manual.
- Troca sleeps fixos por `WebDriverWait` para `document.readyState` e presença de `article` da timeline.
- Faz scroll incremental e acumula posts entre estados do DOM virtualizado.
- Seletores semânticos: `article[data-testid="tweet"]`, fallback `article[role="article"]`, `a[href="/<usuario>/status/<id>"]`, `time` e `data-testid="tweetText"`.
- Ignora fixados, reposts de terceiros e replies.
- Detecta explicitamente login-wall, challenge/CAPTCHA, JavaScript indisponível, navegador recusado, rate limit e erro genérico do X.
- Em falha, salva automaticamente HTML, texto visível e screenshot em `backend/.radar_x_debug/`.

## Diagnóstico

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\backend"
python scripts\diagnosticar_x.py
```

Se a timeline continuar sem `article`, envie os três arquivos gerados para `@Atletico` dentro de `.radar_x_debug`. Eles mostram exatamente qual página o X entregou ao Chrome headless.
