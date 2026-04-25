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
GEMINI_API_KEY = "CHAVE GEMINI"
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
        Você é um assistente especializado em licitações.
        Analise o PDF e extraia:
        1. Objeto: Um resumo curto (uma frase) do que é a obra.
        2. Valor total estimado.
        3. Área em metros quadrados (m²).
        4. Prazo de execução.
        5. Empresa vencedora (se houver).
        6. Tipo da obra (Construção, Reparo, Pavimentação, Saneamento, Iluminação ou Outros).
        
        Responda APENAS JSON:
        {
            "objeto": "texto",
            "valor": 0.0,
            "metros_quadrados": "texto",
            "prazo": "texto",
            "empresa": "texto",
            "tipo_obra": "texto"
        }
        """
        
        resposta = client.models.generate_content(model='gemini-2.5-flash', contents=[arquivo_pdf, prompt])
        texto_limpo = resposta.text.replace("```json", "").replace("```", "").strip()
        dados_ia = json.loads(texto_limpo)
        
        client.files.delete(name=arquivo_pdf.name)
        return dados_ia
        
    except Exception as e:
        print(f"       [!] Erro na IA: {e}")
        return None

# =========================================================
# FUNÇÕES DE PROCESSAMENTO E UPLOAD (CORRIGIDO 409)
# =========================================================

def processar_e_enviar_supabase(caminho_arquivo, numero_licitacao):
    try:
        # CORREÇÃO 409: Criamos um nome único usando o número da licitação
        # Substituímos "/" por "-" para não dar erro de pasta no SO
        num_seguro = numero_licitacao.replace("/", "-")
        nome_original = os.path.basename(caminho_arquivo)
        nome_arquivo_unico = f"{num_seguro}_{nome_original}"
        
        print(f"       -> Iniciando extração Inteligente para {numero_licitacao}...")
        dados = extrair_dados_com_gemini(caminho_arquivo)
        
        if not dados:
            print("       [!] IA não retornou dados. Pulando registro.")
            return

        print("       -> Fazendo upload para o Supabase Storage (Nome Único)...")
        with open(caminho_arquivo, 'rb') as f:
            # Usamos o nome único para evitar o erro 409
            supabase.storage.from_('editais-obras').upload(nome_arquivo_unico, f)
        
        url_publica = supabase.storage.from_('editais-obras').get_public_url(nome_arquivo_unico)
        
        print("       -> Salvando registro no Banco de Dados...")
        registro = {
            "numero_licitacao": numero_licitacao,
            "url_pdf": url_publica,
            "objeto": dados.get("objeto", "Não extraído"),
            "valor": dados.get("valor"),
            "metros_quadrados": dados.get("metros_quadrados"),
            "prazo": dados.get("prazo"),
            "trabalhadores": str(dados.get("trabalhadores", "Não especificado")),
            "empresa": dados.get("empresa"),
            "tipo_obra": dados.get("tipo_obra")
        }
        
        supabase.table("licitacoes").insert(registro).execute()
        print(f"       -> ✅ Sucesso! Objeto salvo: {registro['objeto'][:40]}...")
        
        os.remove(caminho_arquivo)
        
    except Exception as e:
        # Se o erro for de duplicidade, avisamos mas não travamos o código
        if "Duplicate" in str(e):
            print(f"       [!] Aviso: O arquivo {nome_arquivo_unico} já existe no Storage. Pulando upload.")
        else:
            print(f"       [!] Erro crítico na integração: {e}")

# =========================================================
# FASE 1: EXTRAÇÃO (CORREÇÃO DA PAGINAÇÃO)
# =========================================================

# Dentro da função extrair_e_baixar_licitacoes, substitua o bloco da Fase 1:

    try:
        print("--- FASE 1: EXTRAÇÃO DE CONTRATOS ---")
        driver.get("https://transparencia.macae.rj.gov.br/contratacoes/contratos")
        time.sleep(5) 

        # ... (Seu código de configurar filtros continua igual até o clique no 'Buscar') ...
        driver.find_element(By.XPATH, "//button[contains(@class, 'btn') and contains(text(), 'Buscar')]").click()
        time.sleep(10)

        pagina_atual = 1
        
        # LÓGICA DE PAGINAÇÃO BLINDADA
        while True:
            print(f"\nLendo a página {pagina_atual}...")
            
            # Espera as linhas da tabela carregarem
            wait.until(EC.presence_of_element_located((By.XPATH, "//table/tbody/tr[@role='row']")))
            linhas = driver.find_elements(By.XPATH, "//table/tbody/tr[@role='row']")

            for linha in linhas:
                try:
                    coluna_licitacao = linha.find_element(By.XPATH, "./td[6]")
                    numero = coluna_licitacao.text.strip()
                    if numero and numero != "..." and numero not in numeros_licitacao:
                        numeros_licitacao.append(numero)
                except:
                    continue

            # Tentativa de ir para a próxima página
            try:
                xpath_botao_proximo = "//a[contains(text(), 'Próxima') or contains(text(), 'Próximo')]"
                # Verifica se o botão existe
                botoes = driver.find_elements(By.XPATH, xpath_botao_proximo)
                
                if not botoes:
                    print("-> Fim das páginas: Botão 'Próximo' não encontrado.")
                    break
                
                botao_proximo = botoes[0]
                classe_pai = botao_proximo.find_element(By.XPATH, "..").get_attribute("class")

                # Se o botão estiver desabilitado, paramos
                if "disabled" in classe_pai:
                    print("-> Chegamos na última página.")
                    break

                # Clique Seguro
                driver.execute_script("arguments[0].click();", botao_proximo)
                pagina_atual += 1
                
                # Pausa para o site processar a troca de página
                time.sleep(random.uniform(6, 10))
                
            except Exception as e:
                print(f"-> Parando paginação: {e}")
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