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
            aba_tabela = driver.current_window_handle
            
            # Pega os IDs da página atual
            linhas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            ids_da_pagina = []
            for linha in linhas:
                id_contrato = linha.get_attribute("id")
                if id_contrato:
                    ids_da_pagina.append(id_contrato)
            
            # Garante que temos uma segunda aba aberta APENAS UMA VEZ para ler os contratos
            if len(driver.window_handles) == 1:
                driver.switch_to.new_window('tab')
            aba_leitura = driver.window_handles[1]
            
            # Abre e lê cada contrato
            for indice, id_contrato in enumerate(ids_da_pagina):
                
                # ESTRATÉGIA DE LOTES: A cada 10 contratos, dá uma pausa longa para esfriar o servidor
                if indice > 0 and indice % 10 == 0:
                    print(f"[{contador_linha}] Pausa estratégica de 15s para não acionar o firewall...")
                    time.sleep(15)
                else:
                    time.sleep(random.uniform(3.5, 6.5)) # Pausa normal um pouco maior
                
                url_direta = f"https://transparencia.macae.rj.gov.br/default/contratacoes/mostrarcontratos?id={id_contrato}"
                
                # LOOP DE TENTATIVA E RECUPERAÇÃO DO 403
                while True:
                    try:
                        driver.switch_to.window(aba_leitura)
                        driver.get(url_direta)

                        # Verifica se tomamos o bloqueio 403 olhando o texto bruto da tela
                        texto_tela = driver.find_element(By.TAG_NAME, "body").text
                        if "403 Forbidden" in texto_tela or "Request forbidden" in texto_tela:
                            print("\n" + "!"*80)
                            print(f"🚨 BLOQUEIO 403 DETECTADO NO CONTRATO {contador_linha}!")
                            print("O servidor bloqueou seu IP temporariamente.")
                            print("SOLUÇÃO:")
                            print("1. Roteie a internet do seu celular (4G) para o computador.")
                            print("   (Ou ligue/desligue o modo avião no celular para trocar o IP do 4G).")
                            print("2. Pressione ENTER aqui no terminal para o robô tentar ler novamente.")
                            print("!"*80 + "\n")
                            input("Pressione ENTER quando tiver trocado a rede para continuar...")
                            continue # Volta pro início do 'while True' e tenta carregar o mesmo link!

                        # Se não tem 403, segue a vida e procura a caixa do objeto
                        caixa_objeto = wait.until(EC.presence_of_element_located((By.ID, "dsobjeto")))
                        
                        texto_objeto = caixa_objeto.get_attribute("value")
                        if not texto_objeto:
                            texto_objeto = caixa_objeto.text
                            
                        texto_objeto = texto_objeto.replace('\n', ' ').strip()
                        if not texto_objeto:
                            texto_objeto = "ERRO: O campo de objeto estava vazio."

                        aprovado, status = eh_obra_real(texto_objeto)
                        print(f"{contador_linha}. {status} -> {texto_objeto[:100]}...\n{'-'*80}")
                        
                        resultados_completos.append({
                            "id_tabela": contador_linha,
                            "id_macae": id_contrato,
                            "classificacao": status,
                            "objeto": texto_objeto,
                            "url": url_direta
                        })
                        
                        contador_linha += 1
                        break # Sai do loop de tentativa e vai para o próximo contrato (for)

                    except Exception as e:
                        print(f"{contador_linha}. ERRO TÉCNICO -> Link {url_direta}. Tentando pular... Detalhe: {str(e)[:50]}")
                        contador_linha += 1
                        break # Se der um erro bizarro que não é 403, ele pula o contrato
                
            # Fim da página de contratos, volta para a tabela principal para clicar em "Próximo"
            driver.switch_to.window(aba_tabela)
            
            # Fim da página de contratos, volta para a tabela principal para clicar em "Próximo"
            driver.switch_to.window(aba_tabela)
            
            # --- CÓDIGO DE PAGINAÇÃO ---
            try:
                print("\nMudando para a próxima página da tabela...")
                botao_proximo = driver.find_element(By.XPATH, "//li[contains(@class, 'next')]/a | //a[contains(text(), 'Próximo')]")
                
                # Se o botão "Próximo" estiver desativado, significa que chegamos na última página
                if "disabled" in botao_proximo.get_attribute("class") or not botao_proximo.is_displayed():
                    print("Última página alcançada!")
                    break 
                
                # Clica no botão e espera a nova tabela carregar
                driver.execute_script("arguments[0].scrollIntoView();", botao_proximo)
                driver.execute_script("arguments[0].click();", botao_proximo)
                time.sleep(5) 
                
            except Exception as e:
                print("Não encontrou mais páginas. Encerrando a varredura.")
                break # Sai do loop gigante "while True" e vai salvar o CSV

    finally:
        driver.quit()
        df = pd.DataFrame(resultados_completos)
        df.to_csv("historico_completo_macae.csv", index=False)
        print(f"\nVarredura finalizada com sucesso! {len(df)} obras prontas no CSV.")

if __name__ == "__main__":
    extrair_contratos_macae_avancado()