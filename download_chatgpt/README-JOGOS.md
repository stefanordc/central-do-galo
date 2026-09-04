# Página Jogos - Central do Galo

## Arquivos
Copie/extrate o pacote sobre a raiz do projeto `central-do-galo`.

## 1. Registrar a rota
Na raiz do projeto:

```powershell
python instalar_router_jogos.py
```

O script cria um backup `backend/app/main.py.bak_jogos`.

## 2. Configurar API-Football
Adicione ao `backend/.env`:

```env
API_FOOTBALL_KEY=SUA_CHAVE
API_FOOTBALL_TEAM_ID=
API_FOOTBALL_TIMEZONE=America/Sao_Paulo
```

Se `API_FOOTBALL_TEAM_ID` ficar vazio, o sistema tenta localizar o Atlético-MG.

## 3. Importação inicial
Com o backend parado:

```powershell
cd backend
python scripts\sincronizar_jogos_api.py --modo inicial
```

## 4. Atualizações normais
```powershell
python scripts\sincronizar_jogos_api.py --modo atual
```

## 5. Preencher autores de gols progressivamente
```powershell
python scripts\sincronizar_jogos_api.py --modo gols --limite-gols 20
```

## 6. Iniciar
```powershell
python run.py
```

Frontend:
```powershell
cd ..\frontend
npm run dev
```
