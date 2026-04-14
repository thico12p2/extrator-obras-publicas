import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
import time
import random

def eh_obra_real(texto_objeto):
    texto = texto_objeto.lower()
    
    excluir = [
        "aquisição", "compra", "fornecimento", "merenda", "medicamento", 
        "limpeza", "conservação rotineira", "locação", "aluguel", 
        "licenciamento", "roçada", "capina", "varrição", "manutenção preventiva"
    ]
    
    incluir = [
        "construção", "pavimentação", "reforma", "revitalização", 
        "drenagem", "recapeamento", "terraplenagem", "urbanização", 
        "ampliação", "restauração", "contenção", "saneamento", "obra"
    ]

    if any(termo in texto for termo in excluir):
        return False, "FALSO (Serviço/Compra)"

    if any(termo in texto for termo in incluir):
        return True, "VERDADEIRO (Obra de Engenharia)"

    return False, "FALSO (Fora do escopo)"

def extrair_contratos_macae_avancado():
    # 1. PREPARAÇÃO DO NAVEGADOR INVISÍVEL
    options = uc.ChromeOptions()
    print("Iniciando o navegador invisível...")
    
    # Inicia apenas UMA vez usando o undetected_chromedriver
    driver = uc.Chrome(options=options)
    wait = WebDriverWait(driver, 15)

    print("Acessando o portal de Macaé...")
    driver.get("https://transparencia.macae.rj.gov.br/contratacoes/contratos?tpcontrato=1")
    
    resultados_completos = []
    contador_linha = 1

    try:
        print("Clicando em Buscar...")
        botao_buscar = wait.until(EC.element_to_be_clickable((By.ID, "btn-buscar")))
        botao_buscar.click()

        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        time.sleep(3) 
        print("Tabela carregada! Iniciando varredura...\n" + "="*80)

        while True:
            janela_principal = driver.current_window_handle
            
            # Pega os IDs da página atual
            linhas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            ids_da_pagina = []
            for linha in linhas:
                id_contrato = linha.get_attribute("id")
                if id_contrato:
                    ids_da_pagina.append(id_contrato)
            
            # Abre e lê cada contrato
            for id_contrato in ids_da_pagina:
                # Pausa aleatória para imitar um humano e evitar bloqueios
                time.sleep(random.uniform(2.5, 5.5))
                
                url_direta = f"https://transparencia.macae.rj.gov.br/default/contratacoes/mostrarcontratos?id={id_contrato}"
                
                try:
                    # 2. NOVA ESTRATÉGIA DE ABA (Não bloqueada por pop-ups)
                    # O próprio Selenium abre uma aba em branco e muda o foco para ela
                    driver.switch_to.new_window('tab')
                    # Carrega o link direto na aba nova
                    driver.get(url_direta)

                    # 3. LEITURA CIRÚRGICA DO TEXTO (Pelo ID "dsobjeto")
                    caixa_objeto = wait.until(EC.presence_of_element_located((By.ID, "dsobjeto")))
                    
                    texto_objeto = caixa_objeto.get_attribute("value")
                    if not texto_objeto:
                        texto_objeto = caixa_objeto.text
                        
                    texto_objeto = texto_objeto.replace('\n', ' ').strip()

                    if not texto_objeto:
                        texto_objeto = "ERRO: O campo de objeto estava vazio no site."

                    # Avalia o filtro do seu projeto
                    aprovado, status = eh_obra_real(texto_objeto)
                    
                    print(f"{contador_linha}. {status} -> {texto_objeto}\n{'-'*80}")
                    
                    resultados_completos.append({
                        "id_tabela": contador_linha,
                        "id_macae": id_contrato,
                        "classificacao": status,
                        "objeto": texto_objeto,
                        "url": url_direta
                    })

                except Exception as e:
                    # Se der erro, tira foto pra gente ver
                    print(f"{contador_linha}. ERRO NA EXTRAÇÃO -> Link {url_direta}. Detalhe: {str(e)[:50]}...\n{'-'*80}")
                    nome_foto = f"erro_contrato_{contador_linha}.png"
                    driver.save_screenshot(nome_foto)
                    print(f"-> Tirei um print e salvei como '{nome_foto}'.\n" + "-"*80)
                
                finally:
                    contador_linha += 1
                    # Fecha a aba perfeitamente e volta pra tabela principal
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(janela_principal)

            # Tenta ir para a próxima página da tabela
            try:
                botao_proximo = driver.find_element(By.XPATH, "//li[contains(@class, 'next')]/a | //a[contains(text(), 'Próximo')]")
                if "disabled" in botao_proximo.get_attribute("class") or not botao_proximo.is_displayed():
                    break
                driver.execute_script("arguments[0].scrollIntoView();", botao_proximo)
                driver.execute_script("arguments[0].click();", botao_proximo)
                time.sleep(3) 
            except:
                break 

    finally:
        driver.quit()
        df = pd.DataFrame(resultados_completos)
        df.to_csv("historico_completo_macae.csv", index=False)
        print(f"\nVarredura finalizada com sucesso! {len(df)} obras prontas no CSV.")

if __name__ == "__main__":
    extrair_contratos_macae_avancado()