import time
import re
import json
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# ==========================================
# >>> VARIÁVEL PARA INFORMAR O @ DA CONTA <<<
# ==========================================
CONTA_ALVO = "Atletico"  # Troque aqui pelo perfil desejado
# ==========================================

class ScraperXFinal:
    def __init__(self):
        self.driver = None
        self.tweets_coletados = []
        
    def configurar_driver(self):
        """Configura o driver detectando automaticamente a versão do Chrome."""
        options = uc.ChromeOptions()
        
        # Headless mode (novo método para Chrome 151+)
        options.add_argument("--headless=new")
        
        # Configurações anti-detecção
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-logging")
        options.add_argument("--log-level=3")
        
        # Preferências para parecer mais humano
        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.geolocation": 2,
            "profile.default_content_setting_values.media_stream": 2,
            "profile.default_content_setting_values.images": 1,
        }
        options.add_experimental_option("prefs", prefs)
        
        # Cria o driver SEM especificar versão (detecta automaticamente)
        self.driver = uc.Chrome(options=options, use_subprocess=True)
        
        # Remove flags de automação
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['pt-BR', 'pt', 'en-US', 'en']
                });
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
            """
        })
        
    def esperar_delay_humano(self, min_seg=0.5, max_seg=2.0):
        """Espera tempo aleatório para simular humano."""
        time.sleep(random.uniform(min_seg, max_seg))
        
    def simular_atividade_humana(self):
        """Simula atividade humana na página."""
        # Scroll suave
        self.driver.execute_script(f"""
            window.scrollBy({{
                top: {random.randint(100, 400)},
                behavior: 'smooth'
            }});
        """)
        
        # Move o mouse virtualmente
        self.driver.execute_script(f"""
            var x = {random.randint(100, 800)};
            var y = {random.randint(100, 600)};
            var moveEvent = new MouseEvent('mousemove', {{
                view: window,
                bubbles: true,
                cancelable: true,
                clientX: x,
                clientY: y
            }});
            document.dispatchEvent(moveEvent);
        """)
        
    def aguardar_tweets(self, timeout=30):
        """Aguarda os tweets carregarem com verificação robusta."""
        tempo_inicial = time.time()
        tentativas = 0
        
        while time.time() - tempo_inicial < timeout:
            try:
                # Verifica múltiplos seletores
                seletores = [
                    'article[data-testid="tweet"]',
                    'div[data-testid="tweet"]',
                    'article[data-testid="tweet"] div[data-testid="tweetText"]'
                ]
                
                for seletor in seletores:
                    elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                    if len(elementos) > 0:
                        return True
                
                # Verifica bloqueio
                page_text = self.driver.page_source.lower()
                bloqueios = [
                    "something went wrong",
                    "rate limit exceeded",
                    "twitter is over capacity",
                    "this request was rate limited"
                ]
                
                for bloqueio in bloqueios:
                    if bloqueio in page_text:
                        print(f"⚠️ Detectado bloqueio: {bloqueio}")
                        return False
                
                # Scroll e espera
                self.simular_atividade_humana()
                tentativas += 1
                
                if tentativas % 3 == 0:
                    print(f"🔄 Ainda aguardando... ({tentativas} tentativas)")
                    
                time.sleep(2)
                
            except Exception as e:
                time.sleep(1)
                continue
                
        return False
        
    def extrair_texto_completo(self, article):
        """Extrai texto mantendo formatação e emojis."""
        texto_div = article.find("div", attrs={"data-testid": "tweetText"})
        
        if not texto_div:
            return "Sem texto disponível"
            
        # Captura todo o texto incluindo emojis
        texto_partes = []
        
        # Pega todos os spans e imgs (emojis)
        for elemento in texto_div.find_all(["span", "img"]):
            if elemento.name == "img":
                alt = elemento.get("alt", "")
                if alt:
                    texto_partes.append(alt)
            else:
                texto_partes.append(elemento.get_text())
                
        texto_completo = "".join(texto_partes)
        
        # Se não conseguiu extrair, usa get_text normal
        if not texto_completo.strip():
            texto_completo = texto_div.get_text()
            
        return texto_completo.strip()
        
    def extrair_metricas(self, article):
        """Extrai métricas de engajamento."""
        metricas = {}
        
        # Busca elementos com aria-label
        elementos_metricas = article.find_all(attrs={"aria-label": True})
        
        for elemento in elementos_metricas:
            aria = elemento.get("aria-label", "")
            
            if "resposta" in aria.lower():
                numeros = re.findall(r'[\d.]+', aria)
                if numeros:
                    metricas["respostas"] = numeros[0]
                    
            elif "repost" in aria.lower():
                numeros = re.findall(r'[\d.]+', aria)
                if numeros:
                    metricas["reposts"] = numeros[0]
                    
            elif "curtid" in aria.lower():
                numeros = re.findall(r'[\d.]+', aria)
                if numeros:
                    metricas["curtidas"] = numeros[0]
                    
        return metricas
        
    def extrair_imagens(self, article):
        """Extrai URLs de imagens em alta qualidade."""
        imagens = []
        
        for img in article.find_all("img"):
            src = img.get("src", "")
            if "pbs.twimg.com/media" in src:
                # Converte para qualidade máxima
                if "name=" in src:
                    src = re.sub(r'name=\w+', 'name=4096x4096', src)
                elif "?" in src:
                    src = re.sub(r'\?.*', '?format=jpg&name=4096x4096', src)
                else:
                    src += "?format=jpg&name=4096x4096"
                    
                if src not in imagens:
                    imagens.append(src)
                    
        return imagens
        
    def processar_tweets(self):
        """Processa os tweets da página."""
        html = self.driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        
        articles = soup.find_all("article", attrs={"data-testid": "tweet"})
        print(f"📊 {len(articles)} tweets encontrados")
        
        for i, article in enumerate(articles[:3], 1):
            tweet = {}
            
            # Extrai URL e ID
            link = article.find("a", href=re.compile(r'/status/\d+'))
            if link:
                match = re.search(r'/status/(\d+)', link["href"])
                if match:
                    tweet["id"] = match.group(1)
                    tweet["url"] = f"https://x.com/{CONTA_ALVO}/status/{match.group(1)}"
                    
            # Extrai texto
            tweet["texto"] = self.extrair_texto_completo(article)
            
            # Extrai timestamp
            time_tag = article.find("time")
            if time_tag:
                tweet["timestamp"] = time_tag.get("datetime", "")
                
            # Extrai imagens
            tweet["imagens"] = self.extrair_imagens(article)
            
            # Extrai métricas
            tweet.update(self.extrair_metricas(article))
            
            self.tweets_coletados.append(tweet)
            
    def executar(self):
        """Executa o scraping completo."""
        try:
            print("🔄 Inicializando Chrome headless...")
            self.configurar_driver()
            
            conta_limpa = CONTA_ALVO.replace("@", "")
            url = f"https://x.com/{conta_limpa}"
            
            print(f"📡 Acessando @{conta_limpa}...")
            self.driver.get(url)
            
            # Espera inicial
            self.esperar_delay_humano(3, 5)
            
            # Simula scroll para carregar conteúdo
            print("🔄 Carregando conteúdo...")
            for i in range(5):
                self.simular_atividade_humana()
                self.esperar_delay_humano(1, 2)
                
            # Aguarda tweets
            if self.aguardar_tweets():
                print("✅ Conteúdo carregado!")
                self.processar_tweets()
            else:
                print("⚠️ Timeout ao carregar tweets")
                # Tenta uma última vez
                print("🔄 Última tentativa...")
                self.driver.refresh()
                self.esperar_delay_humano(5, 8)
                if self.aguardar_tweets(timeout=20):
                    self.processar_tweets()
                    
            return self.tweets_coletados
            
        except Exception as e:
            print(f"❌ Erro: {str(e)[:200]}")
            return []
            
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    print("🔒 Navegador fechado")
                except:
                    pass
                    
    def exibir(self):
        """Exibe resultados formatados."""
        if not self.tweets_coletados:
            print("\n❌ Nenhum tweet extraído")
            return
            
        print(f"\n✅ SUCESSO! {len(self.tweets_coletados)} tweets de @{CONTA_ALVO}")
        print("=" * 80)
        
        for i, tweet in enumerate(self.tweets_coletados, 1):
            print(f"\n📝 TWEET {i}")
            print("-" * 50)
            
            if tweet.get("url"):
                print(f"🔗 {tweet['url']}")
                
            if tweet.get("timestamp"):
                print(f"🕐 {tweet['timestamp']}")
                
            print(f"\n📄 TEXTO:")
            print(tweet["texto"])
            
            if tweet.get("imagens"):
                print(f"\n🖼️ {len(tweet['imagens'])} imagens:")
                for img in tweet["imagens"]:
                    print(f"  {img}")
                    
            metricas = []
            if tweet.get("respostas"):
                metricas.append(f"💬 {tweet['respostas']}")
            if tweet.get("reposts"):
                metricas.append(f"🔄 {tweet['reposts']}")
            if tweet.get("curtidas"):
                metricas.append(f"❤️ {tweet['curtidas']}")
                
            if metricas:
                print(f"\n📊 {' | '.join(metricas)}")
                
            print("\n" + "=" * 80)

if __name__ == "__main__":
    print("=" * 80)
    print(f"🚀 SCRAPER X/TWITTER - @{CONTA_ALVO}")
    print("=" * 80)
    
    scraper = ScraperXFinal()
    tweets = scraper.executar()
    scraper.exibir()