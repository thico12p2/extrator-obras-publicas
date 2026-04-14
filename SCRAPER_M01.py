import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
import time
import random
import os

def eh_obra_real(texto_objeto):
    texto = texto_objeto.lower()
    excluir = ["aquisição", "compra", "fornecimento", "merenda", "medicamento", "limpeza", "conservação rotineira", "locação", "aluguel", "licenciamento", "roçada", "capina", "varrição", "manutenção preventiva"]
    incluir = ["construção", "pavimentação", "reforma", "revitalização", "drenagem", "recapeamento", "terraplenagem", "urbanização", "ampliação", "restauração", "contenção", "saneamento", "obra"]

    if any(termo in texto for termo in excluir): return False, "FALSO (Serviço/Compra)"
    if any(termo in texto for termo in incluir): return True, "VERDADEIRO (Obra de Engenharia)"
    return False, "FALSO (Fora do escopo)"

# ==============================================================================
# ETAPA 1: O BATEDOR (Apenas mapeia os IDs da tabela e salva num arquivo)
# ==============================================================================
# ==============================================================================
# ETAPA 1: O BATEDOR (Apenas mapeia os IDs da tabela e salva num arquivo)
# ==============================================================================
def etapa1_mapear_todos_os_ids():
    print("\n--- ETAPA 1: MAPEANDO A TABELA PRINCIPAL ---")
    driver = uc.Chrome(options=uc.ChromeOptions())
    wait = WebDriverWait(driver, 15)
    driver.get("https://transparencia.macae.rj.gov.br/contratacoes/contratos?tpcontrato=1")
    
    lista_de_ids = []
    ids_da_pagina_anterior = [] # A NOSSA NOVA TRAVA DE SEGURANÇA
    
    try:
        wait.until(EC.element_to_be_clickable((By.ID, "btn-buscar"))).click()
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        time.sleep(3)
        
        pagina = 1
        while True:
            print(f"Mapeando página {pagina}...")
            linhas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            
            ids_desta_pagina = []
            for linha in linhas:
                id_contrato = linha.get_attribute("id")
                if id_contrato:
                    ids_desta_pagina.append(id_contrato)
            
            # TRAVA DE SEGURANÇA: Se a página nova for igual à velha, chegamos no fim real!
            if ids_desta_pagina == ids_da_pagina_anterior:
                print(f"A tabela parou de atualizar! A página {pagina-1} era realmente a última.")
                break
                
            # Se forem IDs novos, salva eles e atualiza a memória
            lista_de_ids.extend(ids_desta_pagina)
            ids_da_pagina_anterior = ids_desta_pagina.copy()
            
            try:
                # Clica em próximo sem se preocupar com a classe disabled
                botao_proximo = driver.find_element(By.XPATH, "//li[contains(@class, 'next')]/a | //a[contains(text(), 'Próximo')]")
                driver.execute_script("arguments[0].scrollIntoView();", botao_proximo)
                driver.execute_script("arguments[0].click();", botao_proximo)
                pagina += 1
                time.sleep(3)
            except:
                break
    finally:
        driver.quit()
        # Remove possíveis duplicatas por garantia
        lista_de_ids = list(dict.fromkeys(lista_de_ids))
        
        df_ids = pd.DataFrame(lista_de_ids, columns=["id_contrato"])
        df_ids.to_csv("lista_ids_macae.csv", index=False)
        print(f"✅ Etapa 1 Concluída! {len(lista_de_ids)} IDs mapeados e salvos no arquivo 'lista_ids_macae.csv'.\n")
# ==============================================================================
# ETAPA 2: O ESPECIALISTA COM AMNÉSIA (Lê os contratos burlando o firewall)
# ==============================================================================
def etapa2_ler_contratos_com_amnesia():
    print("\n--- ETAPA 2: EXTRAÇÃO COM AMNÉSIA DE SESSÃO ---")
    
    if not os.path.exists("lista_ids_macae.csv"):
        print("Erro: Arquivo 'lista_ids_macae.csv' não encontrado. Rode a Etapa 1 primeiro.")
        return

    df_ids = pd.read_csv("lista_ids_macae.csv")
    todos_ids = df_ids["id_contrato"].tolist()
    
    resultados_completos = []
    
    # Inicia o navegador pela primeira vez
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    try:
        for indice, id_contrato in enumerate(todos_ids):
            numero_real = indice + 1
            
            # 🚨 A MÁGICA ACONTECE AQUI: A cada 15 contratos, destrói as provas!
            if indice > 0 and indice % 15 == 0:
                print(f"\n[{numero_real}] 🔄 Limpando rastros... Fechando e reabrindo o navegador para zerar o firewall!")
                driver.quit() # Mata o navegador e os cookies
                time.sleep(5) # Respira fundo
                novas_opcoes = uc.ChromeOptions()
                driver = uc.Chrome(options=novas_opcoes)
                wait = WebDriverWait(driver, 10)
            
            # Pequena pausa humana entre um e outro
            time.sleep(random.uniform(2.5, 4.5))
            url_direta = f"https://transparencia.macae.rj.gov.br/default/contratacoes/mostrarcontratos?id={id_contrato}"
            
            try:
                driver.get(url_direta)
                
                # Se ainda assim tomar 403 (IP queimado), ele pausa e avisa
                texto_tela = driver.find_element(By.TAG_NAME, "body").text
                if "403 Forbidden" in texto_tela or "Request forbidden" in texto_tela:
                    print(f"\n🚨 [ERRO 403] O IP foi bloqueado no contrato {numero_real}!")
                    input("Mude para a rede 4G do celular e aperte ENTER para o robô tentar de novo...")
                    driver.get(url_direta) # Tenta recarregar

                caixa_objeto = wait.until(EC.presence_of_element_located((By.ID, "dsobjeto")))
                texto_objeto = caixa_objeto.get_attribute("value")
                if not texto_objeto: texto_objeto = caixa_objeto.text
                texto_objeto = texto_objeto.replace('\n', ' ').strip()
                if not texto_objeto: texto_objeto = "ERRO: Campo vazio."

                aprovado, status = eh_obra_real(texto_objeto)
                print(f"{numero_real}. {status} -> {texto_objeto[:80]}...")
                
                resultados_completos.append({
                    "id_tabela": numero_real,
                    "id_macae": id_contrato,
                    "classificacao": status,
                    "objeto": texto_objeto,
                    "url": url_direta
                })

            except Exception as e:
                print(f"{numero_real}. ERRO TÉCNICO -> Pulando contrato. Detalhe: {str(e)[:40]}")

    finally:
        # Se der algum erro crítico (sua internet cair, etc), ele SALVA O QUE JÁ FEZ
        driver.quit()
        if resultados_completos:
            df = pd.DataFrame(resultados_completos)
            df.to_csv("historico_completo_macae.csv", index=False)
            print(f"\n✅ Varredura salva! {len(df)} contratos lidos no CSV.")

if __name__ == "__main__":
    # Rodamos primeiro o mapeamento, e depois a leitura!
    etapa1_mapear_todos_os_ids()
    etapa2_ler_contratos_com_amnesia()