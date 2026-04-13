import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

def eh_obra_real(texto_objeto):
    texto = texto_objeto.lower()
    
    # 1. Termos de Exclusão (Se tiver isso, o script pula o contrato)
    # Usamos termos compostos para não bloquear obras reais (ex: não bloquear "fornecimento de material e mão de obra")
    excluir = [
        "aquisição", "compra", "fornecimento de peças", "fornecimento de pneus", 
        "merenda", "medicamento", "limpeza urbana", "conservação rotineira",
        "locação de veículos", "aluguel de software", "licenciamento",
        "roçada", "capina", "varrição", "manutenção preventiva de ar"
    ]
    
    # 2. Palavras de Inclusão (Obras reais de engenharia)
    incluir = [
        "construção", "pavimentação", "reforma", "revitalização", 
        "drenagem", "recapeamento", "terraplenagem", "urbanização", 
        "ampliação", "restauração", "contenção de encosta", "saneamento"
    ]

    # Verifica se é um falso positivo (Compra/Serviço rotineiro)
    if any(termo in texto for termo in excluir):
        return False, "Bloqueado por exclusão"

    # Verifica se tem alguma palavra-chave de engenharia
    palavras_encontradas = [termo for termo in incluir if termo in texto]
    if palavras_encontradas:
        return True, f"Aprovado: {palavras_encontradas[0]}"

    return False, "Fora do escopo"

def extrair_contratos_macae_avancado():
    options = Options()
    # options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 15)

    url_lista = "https://transparencia.macae.rj.gov.br/contratacoes/contratos?tpcontrato=1"
    driver.get(url_lista)

    obras_validadas = []

    try:
        while True:
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
            linhas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            
            for i in range(len(linhas)):
                linhas_atualizadas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                linha = linhas_atualizadas[i]
                janela_principal = driver.current_window_handle
                
                try:
                    # Encontra o link de detalhes daquela linha específica
                    botao = linha.find_element(By.CSS_SELECTOR, "a[href*='mostrarcontratos']")
                    link_contrato = botao.get_attribute("href")
                    
                    # Abre uma nova aba diretamente com o link (mais rápido e estável que clicar)
                    driver.execute_script(f"window.open('{link_contrato}', '_blank');")
                    wait.until(EC.number_of_windows_to_be(2))
                    driver.switch_to.window(driver.window_handles[1])

                    # Estratégia para pegar o texto logo após a palavra "Objeto:"
                    # Procura qualquer elemento que contenha "Objeto" e tenta pegar o texto do pai ou irmão seguinte
                    elemento_objeto = wait.until(EC.presence_of_element_located(
                        (By.XPATH, "//*[contains(translate(text(), 'OBJETO', 'objeto'), 'objeto')]/..")
                    ))
                    texto_completo = elemento_objeto.text
                    
                    # Limpa a string para pegar apenas o que importa
                    if "Objeto:" in texto_completo:
                        texto_limpo = texto_completo.split("Objeto:")[1].strip()
                    else:
                        texto_limpo = texto_completo

                    # Passa pelo nosso Super Filtro
                    aprovado, motivo = eh_obra_real(texto_limpo)
                    
                    if aprovado:
                        print(f"✅ {motivo} -> {texto_limpo[:60]}...")
                        obras_validadas.append({
                            "Objeto": texto_limpo,
                            "Link": link_contrato
                        })
                    else:
                        print(f"❌ {motivo} ignorado.")

                except Exception as e:
                    print("Erro ao processar linha.")
                
                finally:
                    # Garante que a aba secundária feche e volte para a principal
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(janela_principal)

            # Paginação
            try:
                botao_proximo = driver.find_element(By.XPATH, "//li[contains(@class, 'next')]/a | //a[contains(text(), 'Próximo')]")
                if "disabled" in botao_proximo.get_attribute("class"):
                    break
                # Rola a tela até o botão para evitar erro de clique interceptado
                driver.execute_script("arguments[0].scrollIntoView();", botao_proximo)
                botao_proximo.click()
                time.sleep(3) 
            except:
                break

    finally:
        driver.quit()
        df = pd.DataFrame(obras_validadas)
        # Salva o arquivo pronto para ser importado no Supabase depois
        df.to_csv("obras_macae_limpas.csv", index=False)
        print(f"\nExtração concluída! {len(df)} obras de engenharia reais filtradas.")

if __name__ == "__main__":
    extrair_contratos_macae_avancado()