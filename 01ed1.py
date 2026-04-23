import os
import re
import time
import glob
import pdfplumber
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

# =========================================================
# CONFIGURAÇÕES DO SUPABASE 
# =========================================================
from supabase import create_client, Client

SUPABASE_URL = "https://cgerjjikajtuohfcgmhd.supabase.co" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNnZXJqamlrYWp0dW9oZmNnbWhkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTcxMjIxMSwiZXhwIjoyMDg1Mjg4MjExfQ.DvFfQgH0XDu_GvyZeGNHpz6zIK58BD28lbSvtQ-uCuw"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================================
# FUNÇÕES DE PROCESSAMENTO E UPLOAD
# =========================================================
def pegar_ultimo_arquivo_baixado(pasta):
    arquivos = glob.glob(os.path.join(pasta, '*'))
    if not arquivos: return None
    arquivos_validos = [f for f in arquivos if not f.endswith('.crdownload') and not f.endswith('.tmp')]
    if not arquivos_validos: return None
    return max(arquivos_validos, key=os.path.getctime)

def extrair_dados_pdf(caminho_pdf):
    dados = {"objeto": "Conteúdo não extraído", "valor": None}
    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            if len(pdf.pages) > 0:
                primeira_pagina = pdf.pages[0].extract_text()
                if primeira_pagina:
                    dados["objeto"] = primeira_pagina[:250].replace('\n', ' ') + "..."
                    valores = re.findall(r'R\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})', primeira_pagina)
                    if valores:
                        valor_str = valores[0].replace('.', '').replace(',', '.')
                        dados["valor"] = float(valor_str)
    except Exception as e:
        print(f"       [!] Erro na leitura do PDF: {e}")
    
    return dados

def processar_e_enviar_supabase(caminho_arquivo, numero_licitacao):
    try:
        nome_arquivo = os.path.basename(caminho_arquivo)
        
        print("       -> Extraindo dados do PDF...")
        dados_pdf = extrair_dados_pdf(caminho_arquivo)
        
        print("       -> Fazendo upload para o Supabase Storage...")
        with open(caminho_arquivo, 'rb') as f:
            supabase.storage.from_('editais-obras').upload(nome_arquivo, f)
        
        url_publica = supabase.storage.from_('editais-obras').get_public_url(nome_arquivo)
        
        print("       -> Salvando registro no Banco de Dados...")
        registro = {
            "numero_licitacao": numero_licitacao,
            "url_pdf": url_publica,
            "objeto": dados_pdf["objeto"],
            "valor": dados_pdf["valor"]
        }
        supabase.table("licitacoes").insert(registro).execute()
        print("       -> ✅ Sucesso! Documento integrado na nuvem.")
        
        # =========================================================
        # LIMPEZA AUTOMÁTICA DO ARQUIVO LOCAL
        # =========================================================
        os.remove(caminho_arquivo)
        print("       -> 🗑️ Limpeza: Arquivo local apagado do seu Mac.")
        
    except Exception as e:
        print(f"       [!] Erro crítico na integração com Supabase: {e}")

# =========================================================
# FUNÇÃO PRINCIPAL DO SCRAPER
# =========================================================
def extrair_e_baixar_licitacoes():
    pasta_downloads = os.path.expanduser("~/Downloads/Editais_Macae")
    os.makedirs(pasta_downloads, exist_ok=True)

    prefs = {
        "download.default_directory": pasta_downloads,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "profile.default_content_settings.popups": 0
    }
    
    opcoes = webdriver.ChromeOptions()
    opcoes.add_experimental_option("prefs", prefs)
    
    opcoes.add_argument('--disable-blink-features=AutomationControlled')
    opcoes.add_experimental_option("excludeSwitches", ["enable-automation"])
    opcoes.add_experimental_option('useAutomationExtension', False)
    opcoes.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=opcoes)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    wait = WebDriverWait(driver, 25) 

    numeros_licitacao = []

    try:
        print("--- FASE 1: EXTRAÇÃO DE CONTRATOS ---")
        driver.get("https://transparencia.macae.rj.gov.br/contratacoes/contratos")
        time.sleep(5) 

        print("Configurando os filtros...")
        xpath_tipo_contrato = "//select[@id='idtipocontrato']"
        xpath_tipo_licitacao = "//select[@id='idtipolicitacao']"

        elemento_tipo = wait.until(EC.presence_of_element_located((By.XPATH, xpath_tipo_contrato)))
        Select(elemento_tipo).select_by_visible_text("Obras e Serviços de Engenharia")

        elemento_licitacao = wait.until(EC.presence_of_element_located((By.XPATH, xpath_tipo_licitacao)))
        Select(elemento_licitacao).select_by_visible_text("Concorrência Pública")

        driver.find_element(By.XPATH, "//button[contains(@class, 'btn') and contains(text(), 'Buscar')]").click()
        time.sleep(12)

        pagina_atual = 1
        parada = True

        while parada:
            parada = False
            print(f"\nLendo a página {pagina_atual}...")
            linhas = driver.find_elements(By.XPATH, "//table/tbody/tr[@role='row']")

            for linha in linhas:
                try:
                    coluna_licitacao = linha.find_element(By.XPATH, "./td[6]")
                    numero = coluna_licitacao.text.strip()
                    if numero and numero != "...":
                        numeros_licitacao.append(numero)
                except Exception:
                    pass

            try:
                xpath_botao_proximo = "//a[contains(text(), 'Próxima') or contains(text(), 'Próximo')]"
                botao_proximo = driver.find_element(By.XPATH, xpath_botao_proximo)
                classe_botao = botao_proximo.get_attribute("class")
                classe_pai = botao_proximo.find_element(By.XPATH, "..").get_attribute("class")

                if "disabled" in classe_botao or "disabled" in classe_pai:
                    break

                botao_proximo.click()
                pagina_atual += 1
                time.sleep(7) 
            except Exception:
                break

        print(f"-> Sucesso! Total de Licitações extraídas: {len(numeros_licitacao)}")

        if len(numeros_licitacao) == 0:
            return

        print("\n\n--- FASE 2: DOWNLOAD DE EDITAIS E INTEGRAÇÃO SUPABASE ---")
        url_pesquisa_editais = "https://transparencia.macae.rj.gov.br/contratacoes/licitacoespesquisa"

        for numero_bruto in numeros_licitacao:
            numero_limpo = re.sub(r'[a-zA-Z]', '', numero_bruto).strip()
            print(f"\nProcessando Licitação: {numero_bruto} -> Limpo: {numero_limpo}")

            driver.get(url_pesquisa_editais)
            janela_principal = driver.current_window_handle
            time.sleep(4) 

            try:
                xpath_campo_numero = "//input[@placeholder='Número/ano']"
                campo_numero = wait.until(EC.presence_of_element_located((By.XPATH, xpath_campo_numero)))
                campo_numero.clear()
                campo_numero.send_keys(numero_limpo)
            except Exception:
                continue

            driver.find_element(By.XPATH, "//button[contains(text(), 'Buscar')]").click()

            try:
                xpath_tabela_resultados = "//table[contains(@class, 'table')]/tbody/tr"
                wait.until(EC.presence_of_element_located((By.XPATH, xpath_tabela_resultados)))
                time.sleep(4)

                primeira_linha = driver.find_element(By.XPATH, "//table[contains(@class, 'table')]/tbody/tr[1]")

                if "nenhum" in primeira_linha.text.lower() or "empty" in primeira_linha.get_attribute("class"):
                    continue

                elementos_clicaveis = primeira_linha.find_elements(By.XPATH, ".//a | .//button | ./td[1]")

                if len(elementos_clicaveis) > 0:
                    driver.execute_script("arguments[0].click();", elementos_clicaveis[0])
                else:
                    driver.execute_script("arguments[0].click();", primeira_linha)

                time.sleep(4)
                todas_as_abas = driver.window_handles
                if len(todas_as_abas) > 1:
                    driver.switch_to.window(todas_as_abas[-1])

            except Exception:
                continue

            try:
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "tb-anexolicitacao-edital")))
                time.sleep(3)

                todos_anexos = driver.find_elements(By.XPATH, "//table[@id='tb-anexolicitacao-edital']//a")
                botoes_download = []

                for anexo in todos_anexos:
                    texto_visivel = anexo.text.upper()
                    texto_oculto = str(anexo.get_attribute("textContent")).upper()
                    html_interno = str(anexo.get_attribute("innerHTML")).upper()

                    if "EDITAL" in texto_visivel or "EDITAL" in texto_oculto or "EDITAL" in html_interno:
                        botoes_download.append(anexo)

                if len(botoes_download) > 0:
                    for i, botao in enumerate(botoes_download):
                        try:
                            arquivos_antes = len(glob.glob(os.path.join(pasta_downloads, '*')))
                            
                            driver.execute_script("arguments[0].click();", botao)
                            wait_modal = WebDriverWait(driver, 6)
                            xpath_botao_azul_download = "//button[contains(text(), 'Download')]"

                            botao_modal = wait_modal.until(EC.element_to_be_clickable((By.XPATH, xpath_botao_azul_download)))
                            botao_modal.click()

                            print(f"      - Baixando arquivo {i + 1}...")
                            tempo_espera = 0
                            while len(glob.glob(os.path.join(pasta_downloads, '*'))) == arquivos_antes and tempo_espera < 40:
                                time.sleep(1)
                                tempo_espera += 1
                            
                            time.sleep(5) 

                            arquivo_baixado = pegar_ultimo_arquivo_baixado(pasta_downloads)
                            if arquivo_baixado:
                                processar_e_enviar_supabase(arquivo_baixado, numero_limpo)
                            else:
                                print("       [!] Não foi possível localizar o arquivo na pasta de downloads.")

                        except Exception:
                            pass

            except Exception:
                pass

            finally:
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(janela_principal)

        print("\n" + "=" * 50)
        print("✅ PROCESSO TOTAL CONCLUÍDO E SINCRONIZADO COM SUPABASE!")
        print("=" * 50)

    except Exception as e:
        print(f"Ocorreu um erro crítico durante a execução: {e}")

    finally:
        if 'driver' in locals():
            driver.quit()

if __name__ == "__main__":
    extrair_e_baixar_licitacoes()