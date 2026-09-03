# Central do Galo — v14

## Radar do X

A seção **X** foi habilitada no menu principal.

Perfis cadastrados:

- @CentralDoCAM
- @canalbicagalo
- @GaloCareca21
- @pedfaria
- @lucascbretas
- @canaldofrossard
- @LucasTanaka
- @InfoGalo_
- @claudiorez
- @ohenriqueandre
- @faelslim
- @BrenoGalante
- @Igortep

A timeline utiliza o widget oficial do X e solicita as 5 publicações públicas mais recentes de cada perfil. Apenas uma timeline é carregada por vez para evitar deixar a página pesada.

### Backend

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\backend"
python run.py
```

Endpoint dos perfis:

```text
http://127.0.0.1:8000/api/x/contas
```

### Frontend

```powershell
cd "C:\Users\stefano.faria\Desktop\central_galo\central-do-galo\frontend"
npm run dev
```

Abra `http://localhost:3000` e clique em **X**.

> O widget do X só exibe publicações de contas públicas. Bloqueadores de rastreamento/social-media do navegador podem impedir o carregamento do widget; nesse caso o link direto para o perfil continua disponível.
