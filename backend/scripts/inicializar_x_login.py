import logging
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

from app.services.x_scrape_service import XScrapeService


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    profile_dir = XScrapeService.profile_dir()
    print("=== INICIALIZAÇÃO DA SESSÃO DO X ===")
    print(f"Perfil dedicado: {profile_dir}")
    print("Uma janela do Chrome será aberta somente para este login inicial.")

    driver = None
    try:
        driver = webdriver.Chrome(options=XScrapeService.chrome_options(headless=False))
        driver.set_page_load_timeout(60)
        driver.get("https://x.com/login")
        print("\nFaça login normalmente no X nessa janela.")
        input("Quando terminar e estiver vendo sua conta logada, pressione ENTER aqui...")

        driver.get("https://x.com/Atletico")
        time.sleep(6)
        current = (driver.current_url or "").lower()
        articles = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')

        if "/i/flow/login" in current or "/login" in current:
            print("ERRO: a sessão ainda está na tela de login.")
            return 1
        if not articles:
            print(
                "AVISO: login foi salvo, mas o perfil @Atletico ainda não exibiu posts. "
                "Feche o Chrome e rode o diagnóstico para testar em headless."
            )
        else:
            print(f"OK: sessão salva e {len(articles)} post(s) visível(is) no perfil @Atletico.")
        return 0
    except WebDriverException as exc:
        print(f"ERRO ao iniciar o Chrome: {exc}")
        return 1
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
