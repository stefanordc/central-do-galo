# Radar do X — scraping público temporário (v20)

A v20 troca a fonte padrão do Radar do X para `X_SOURCE=scrape`.

## Risco e limite desta solução

Este scraping é um **fallback temporário**, não uma solução oficial de produção. O X pode considerar automação/scraping incompatível com seus Termos de Uso e pode bloquear IPs, exigir login, apresentar CAPTCHA/challenges ou alterar o DOM sem aviso.

O coletor foi deliberadamente construído para **não contornar** essas proteções. Se detectar login obrigatório, challenge, CAPTCHA ou ausência do conteúdo público, ele registra o erro e encerra a tentativa daquela conta.

Medidas de redução de impacto:

- navegador headless, sem login;
- User-Agent identificável;
- apenas 3 posts próprios por conta;
- intervalo padrão de 1 hora;
- atraso de ~7s entre contas;
- cache agressivo no Supabase;
- oEmbed só é chamado quando ainda não existe embed válido no cache;
- não coleta reposts de terceiros nem tweet fixado antigo para compor os 3 recentes;
- não usa proxy rotativo, CAPTCHA solver, cookies roubados, sessão autenticada ou bypass anti-bot.

## Fonte e cache

Fluxo:

```text
x.com/<perfil> (Chrome headless, página pública)
  -> encontra URLs dos 3 posts próprios mais recentes
  -> publish.x.com/oembed
  -> public.posts_x no Supabase
  -> FastAPI
  -> frontend + widgets.js
```

O frontend continua consumindo `/api/x/posts?limit_por_conta=3`; portanto nenhuma alteração de contrato foi necessária.

## Configuração padrão

Nenhuma credencial do X é necessária.

```env
X_SOURCE=scrape
X_SYNC_ENABLED=true
X_SCRAPE_INTERVAL_SECONDS=3600
X_SCRAPE_DELAY_BETWEEN_ACCOUNTS_SECONDS=7
X_SCRAPE_POSTS_PER_ACCOUNT=3
X_SCRAPE_HEADLESS=true
```

## Dependência nova

```powershell
pip install -r requirements.txt
```

O Selenium usa o Selenium Manager para localizar/obter o driver compatível. O Google Chrome precisa estar instalado na máquina.

## Teste primeiro @Atletico

```powershell
python scripts/diagnosticar_x.py
```

O diagnóstico testa `@Atletico` primeiro. Se nenhum embed real for gravado, ele interrompe antes das outras cinco contas de validação.

Sincronização manual completa:

```powershell
python scripts/sincronizar_x.py
```
