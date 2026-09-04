from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "backend" / "app" / "main.py"

if not MAIN.exists():
    raise SystemExit(f"Arquivo não encontrado: {MAIN}")

texto = MAIN.read_text(encoding="utf-8")

marca = "# CENTRAL_DO_GALO_JOGOS_ROUTER"

if marca in texto:
    print("Router de jogos já registrado. Nenhuma alteração necessária.")
    raise SystemExit(0)

backup = MAIN.with_name("main.py.bak_jogos")
backup.write_text(texto, encoding="utf-8")

bloco = """

# CENTRAL_DO_GALO_JOGOS_ROUTER
from app.api.routes import jogos as jogos_routes
app.include_router(jogos_routes.router, prefix="/api")
"""

MAIN.write_text(texto.rstrip() + bloco + "\n", encoding="utf-8")

print("Router /api/jogos registrado com sucesso.")
print(f"Backup criado em: {backup}")
