import os
import re
import time
import glob
import json
import random
from google import genai
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from supabase import create_client, Client

# =========================================================
# CONFIGURAÇÕES DE APIs (SUPABASE E GEMINI)
# =========================================================
SUPABASE_URL = "https://cgerjjikajtuohfcgmhd.supabase.co" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNnZXJqamlrYWp0dW9oZmNnbWhkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTcxMjIxMSwiZXhwIjoyMDg1Mjg4MjExfQ.DvFfQgH0XDu_GvyZeGNHpz6zIK58BD28lbSvtQ-uCuw"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Substitua pela sua chave real
GEMINI_API_KEY = "AIzaSyBeWSsC4Jza9fdDzic2uaDKnUgEAzLFkHc"
client = genai.Client(api_key=GEMINI_API_KEY)

# =========================================================
# FUNÇÕES DE PROCESSAMENTO E UPLOAD
# =========================================================
def pegar_ultimo_arquivo_baixado(pasta):
    arquivos = glob.glob(os.path.join(pasta, '*'))
    if not arquivos: return None
    arquivos_validos = [f for f in arquivos if not f.endswith('.crdownload') and not f.endswith('.tmp')]
    if not arquivos_validos: return None
    return max(arquivos_validos, key=os.path.getctime)

def extrair_dados_com_gemini(caminho_pdf):
    print("       -> Fazendo upload do PDF para o Gemini...")
    dados_formatados = {}
    
    try:
        arquivo_pdf = client.files.upload(file=caminho_pdf)
        
        prompt = """
        Você é um assistente especializado em licitações e obras públicas.
        Analise o documento PDF em anexo e extraia exatamente as seguintes informações. 
        Se uma informação não estiver presente no documento, retorne null para números ou "Não especificado" para textos.
        
        1. Valor total ou global estimado da obra.
        2. A área da obra em metros quadrados (m²). DICA: Essa informação geralmente é encontrada nas seções chamadas "Memorial Descritivo", "Escopo" ou "Planilha Orçamentária".
        3. Previsão de datas de início e fim, ou o prazo de execução (ex: "180 dias", "12 meses").
        4. Quantidade de trabalhadores/funcionários previstos ou exigidos.
        5. Nome da empresa que realizou/venceu o serviço (caso o documento seja um contrato ou já cite a vencedora).
        6. O tipo da obra. Você DEVE classificar obrigatoriamente em UMA destas categorias EXATAS: 
           "Construção (prédios, praças)", "Reparo/Reforma", "Pavimentação", "Saneamento/Drenagem", "Iluminação Pública" ou "Outros".
        
        Responda APENAS com um objeto JSON válido. Não adicione textos antes ou depois.
        Formato obrigatório:
        {
            "valor": 150000.50,
            "metros_quadrados": "150 m²",
            "prazo": "120 dias",
            "trabalhadores": "15",
            "empresa": "Construtora Exemplo LTDA",
            "tipo_obra": "Reparo/Reforma"
        }
        """
        
        print("       -> Analisando documento com IA (buscando múltiplos dados)...")
        resposta = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[arquivo_pdf, prompt]
        )
        
        texto_limpo = resposta.text.replace("```json", "").replace("```", "").strip()
        dados_ia = json.loads(texto_limpo)
        
        dados_formatados = {
            "valor": dados_ia.get("valor"),
            "metros_quadrados": dados_ia.get("metros_quadrados", "Não especificado"),
            "prazo_ou_datas": dados_ia.get("prazo", "Não especificado"),
            "quantidade_trabalhadores": dados_ia.get("trabalhadores", "Não especificado"),
            "empresa_contratada": dados_ia.get("empresa", "Não especificado"),
            "tipo_obra": dados_ia.get("tipo_obra", "Outros")
        }
            
        client.files.delete(name=arquivo_pdf.name)
        
    except Exception as e:
        print(f"       [!] Erro na leitura do PDF pelo Gemini: {e}")
        dados_formatados = {
            "valor": None, "metros_quadrados": "Erro na IA", "prazo_ou_datas": "Erro",
            "quantidade_trabalhadores": "Erro", "empresa_contratada": "Erro", "tipo_obra": "Outros"
        }
    
    print("       -> ⏳ Pausando por 15 segundos para respeitar o limite de requisições da IA...")
    time.sleep(15)
    
    return dados_formatados

def processar_e_enviar_supabase(caminho_arquivo, numero_licitacao):
    try:
        nome_arquivo = os.path.basename(caminho_arquivo)
        
        print("       -> Iniciando extração Inteligente...")
        dados = extrair_dados_com_gemini(caminho_arquivo)
        
        print(f"       -> [IA] Tipo: {dados['tipo_obra']} | Valor: R$ {dados['valor']} | Metragem: {dados['metros_quadrados']}")
        
        print("       -> Fazendo upload para o Supabase Storage...")
        with open(caminho_arquivo, 'rb') as f:
            supabase.storage.from_('editais-obras').upload(nome_arquivo, f)
        
        url_publica = supabase.storage.from_('editais-obras').get_public_url(nome_arquivo)
        
        print("       -> Salvando registro no Banco de Dados...")
        registro = {
            "numero_licitacao": numero_licitacao,
            "url_pdf": url_publica,
            "valor": dados["valor"],
            "metros_quadrados": dados["metros_quadrados"],
            "prazo": dados["prazo_ou_datas"],
            "trabalhadores": str(dados["quantidade_trabalhadores"]), 
            "empresa": dados["empresa_contratada"],
            "tipo_obra": dados["tipo_obra"]
        }
        
        supabase.table("licitacoes").insert(registro).execute()
        print("       -> ✅ Sucesso! Documento integrado na nuvem.")
        
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
    
    # NOVAS CONFIGURAÇÕES DE ESTABILIDADE
    opcoes.add_argument('--no-sandbox')
    opcoes.add_argument('--disable-dev-shm-usage')
    opcoes.add_argument('--disable-blink-features=AutomationControlled')
    opcoes.add_experimental_option("excludeSwitches", ["enable-automation"])
    opcoes.add_experimental_option('useAutomationExtension', False)
    
    opcoes.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=opcoes)
    
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    
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
                time.sleep(random.uniform(5, 9))
            except Exception:
                break

        print(f"-> Sucesso! Total de Licitações extraídas: {len(numeros_licitacao)}")

        if len(numeros_licitacao) == 0:
            return

        print("\n\n--- FASE 2: DOWNLOAD DE EDITAIS E INTEGRAÇÃO SUPABASE ---")
        url_pesquisa_editais = "https://transparencia.macae.rj.gov.br/contratacoes/licitacoespesquisa"

        time.sleep(5)

        for numero_bruto in numeros_licitacao:
            numero_limpo = re.sub(r'[a-zA-Z]', '', numero_bruto).strip()
            print(f"\nProcessando Licitação: {numero_bruto} -> Limpo: {numero_limpo}")

            driver.get(url_pesquisa_editais)
            # Define com clareza a aba principal da iteração
            janela_principal = driver.current_window_handle
            
            time.sleep(random.uniform(3, 7)) 

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
                time.sleep(random.uniform(3, 5))

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
                # NOVA LÓGICA DE GERENCIAMENTO DE JANELAS À PROVA DE FALHAS
                try:
                    abas_abertas = driver.window_handles
                    for aba in abas_abertas:
                        # Fecha TODAS as janelas que não sejam a principal
                        if aba != janela_principal:
                            driver.switch_to.window(aba)
                            driver.close()
                    # Retorna o foco de forma segura para a janela raiz
                    driver.switch_to.window(janela_principal)
                except Exception as e:
                    print(f"       [!] Aviso ao gerenciar janelas: {e}")

        print("\n" + "=" * 50)
        print("✅ PROCESSO TOTAL CONCLUÍDO E SINCRONIZADO!")
        print("=" * 50)

    except Exception as e:
        import traceback
        print(f"Ocorreu um erro crítico durante a execução: {e}")
        traceback.print_exc()

    finally:
        if 'driver' in locals():
            driver.quit()

if __name__ == "__main__":
    extrair_e_baixar_licitacoes()