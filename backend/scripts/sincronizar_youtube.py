import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.pool import close_pool, open_pool
from app.services.video_service import sincronizar_youtube

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> int:
    print("=== CENTRAL DO GALO | YOUTUBE ===")
    print("Fonte: youtube.com via SeleniumBase UC | filtro: Público | sem login")
    open_pool()
    try:
        resultado = sincronizar_youtube()
    finally:
        close_pool()

    print(
        f"fontes={resultado['fontes']} | processados={resultado['processados']} | "
        f"salvos/atualizados={resultado['salvos']}"
    )
    for item in resultado["resultados"]:
        print(
            f"{item['fonte']}: videos={item['videos']} | shorts={item['shorts']} | "
            f"lives={item['lives']} | erros={len(item['erros'])}"
        )
        for erro in item["erros"]:
            print(f"  - {erro}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
