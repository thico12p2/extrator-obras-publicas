import os
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select


def extrair_e_baixar_licitacoes():
    # =========================================================
    # CONFIGURAÇÕES DE DOWNLOAD E INICIALIZAÇÃO
    # =========================================================
    pasta_downloads = r"caminho_para_downloads"
    os.makedirs(pasta_downloads, exist_ok=True)

    prefs = {
        "download.default_directory": pasta_downloads,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    }
    opcoes = webdriver.ChromeOptions()
    opcoes.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=opcoes)
    wait = WebDriverWait(driver, 20)

    numeros_licitacao = []

    try:
        # =========================================================
        # FASE 1: EXTRAÇÃO DE CONTRATOS
        # =========================================================
        print("--- FASE 1: EXTRAÇÃO DE CONTRATOS ---")
        driver.get("https://transparencia.macae.rj.gov.br/contratacoes/contratos")

        print("Configurando os filtros...")
        xpath_tipo_contrato = "//select[@id='idtipocontrato']"
        xpath_tipo_licitacao = "//select[@id='idtipolicitacao']"

        elemento_tipo = wait.until(EC.presence_of_element_located((By.XPATH, xpath_tipo_contrato)))
        Select(elemento_tipo).select_by_visible_text("Obras e Serviços de Engenharia")

        elemento_licitacao = wait.until(EC.presence_of_element_located((By.XPATH, xpath_tipo_licitacao)))
        Select(elemento_licitacao).select_by_visible_text("Concorrência Pública")

        # Clicar em Buscar
        driver.find_element(By.XPATH, "//button[contains(@class, 'btn') and contains(text(), 'Buscar')]").click()
        print("Busca realizada. Iniciando extração dos dados...")
        time.sleep(8)

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

            # Paginação
            try:
                xpath_botao_proximo = "//a[contains(text(), 'Próxima') or contains(text(), 'Próximo')]"
                botao_proximo = driver.find_element(By.XPATH, xpath_botao_proximo)

                classe_botao = botao_proximo.get_attribute("class")
                classe_pai = botao_proximo.find_element(By.XPATH, "..").get_attribute("class")

                if "disabled" in classe_botao or "disabled" in classe_pai:
                    break

                botao_proximo.click()
                pagina_atual += 1
                time.sleep(5)
            except Exception:
                break

        print(f"-> Sucesso! Total de Licitações extraídas: {len(numeros_licitacao)}")

        # =========================================================
        # FASE 2: LIMPEZA E DOWNLOAD DOS EDITAIS
        # =========================================================
        if len(numeros_licitacao) == 0:
            print("Nenhuma licitação encontrada na Fase 1. Encerrando o script.")
            return

        print("\n\n--- FASE 2: DOWNLOAD DE EDITAIS ---")
        url_pesquisa_editais = "https://transparencia.macae.rj.gov.br/contratacoes/licitacoespesquisa"

        for numero_bruto in numeros_licitacao:
            # LIMPEZA
            numero_limpo = re.sub(r'[a-zA-Z]', '', numero_bruto).strip()
            print(f"\nProcessando Licitação: {numero_bruto} -> Limpo: {numero_limpo}")

            driver.get(url_pesquisa_editais)

            # Salva a referência da aba principal do navegador
            janela_principal = driver.current_window_handle

            # FILTRO: Número/Ano
            try:
                xpath_campo_numero = "//input[@placeholder='Número/ano']"
                campo_numero = wait.until(EC.presence_of_element_located((By.XPATH, xpath_campo_numero)))
                campo_numero.clear()
                campo_numero.send_keys(numero_limpo)
            except Exception:
                print("   [!] Erro: Não encontrei o campo de Número.")
                continue

            # BUSCAR
            driver.find_element(By.XPATH, "//button[contains(text(), 'Buscar')]").click()

            # =========================================================
            # PASSO INTERMEDIÁRIO: CLICAR NO RESULTADO
            # =========================================================
            print("   -> Aguardando a lista de resultados da pesquisa...")
            try:
                # Usa um XPath restrito para achar a tabela de resultados correta
                xpath_tabela_resultados = "//table[contains(@class, 'table')]/tbody/tr"
                wait.until(EC.presence_of_element_located((By.XPATH, xpath_tabela_resultados)))
                time.sleep(3)

                primeira_linha = driver.find_element(By.XPATH, "//table[contains(@class, 'table')]/tbody/tr[1]")

                if "nenhum" in primeira_linha.text.lower() or "empty" in primeira_linha.get_attribute("class"):
                    print("   [!] A busca realmente retornou vazia para este número.")
                    continue

                elementos_clicaveis = primeira_linha.find_elements(By.XPATH, ".//a | .//button | ./td[1]")

                if len(elementos_clicaveis) > 0:
                    driver.execute_script("arguments[0].click();", elementos_clicaveis[0])
                else:
                    driver.execute_script("arguments[0].click();", primeira_linha)

                print("   -> Resultado clicado! Verificando abas do navegador...")

                # Verifica se o clique abriu uma nova aba e muda o foco para ela
                time.sleep(3)
                todas_as_abas = driver.window_handles
                if len(todas_as_abas) > 1:
                    driver.switch_to.window(todas_as_abas[-1])
                    print("   -> Nova aba detectada. Foco alterado para os detalhes.")

            except Exception as e:
                print(f"   [!] Erro ao interagir com a tabela de resultados. Log técnico: {e}")
                continue

            # =========================================================
            # ESPERAR OS ANEXOS E BAIXAR
            # =========================================================
            try:
                print("   -> Aguardando a tabela de anexos (editais) carregar...")
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "tb-anexolicitacao-edital")))
                time.sleep(3)

                todos_anexos = driver.find_elements(By.XPATH, "//table[@id='tb-anexolicitacao-edital']//a")
                print(f"   [DEBUG] O robô encontrou {len(todos_anexos)} arquivos no total nesta tabela.")

                botoes_download = []

                for anexo in todos_anexos:
                    texto_visivel = anexo.text.upper()
                    texto_oculto = str(anexo.get_attribute("textContent")).upper()
                    html_interno = str(anexo.get_attribute("innerHTML")).upper()

                    if "EDITAL" in texto_visivel or "EDITAL" in texto_oculto or "EDITAL" in html_interno:
                        botoes_download.append(anexo)

                if len(botoes_download) > 0:
                    print(
                        f"   -> SUCESSO! Identificados {len(botoes_download)} arquivos de EDITAL. Iniciando download...")

                    for i, botao in enumerate(botoes_download):
                        try:
                            driver.execute_script("arguments[0].click();", botao)
                            print(f"      - Arquivo {i + 1} clicado. Esperando janela de cadastro...")

                            wait_modal = WebDriverWait(driver, 6)
                            xpath_botao_azul_download = "//button[contains(text(), 'Download')]"

                            botao_modal = wait_modal.until(
                                EC.element_to_be_clickable((By.XPATH, xpath_botao_azul_download)))
                            botao_modal.click()

                            print(f"      - Cadastro ignorado! Baixando arquivo {i + 1}...")
                            time.sleep(5)

                        except Exception as e:
                            print(f"      - Aviso: A tela de cadastro não apareceu para o arquivo {i + 1}.")
                else:
                    print("   -> Tem arquivos na tabela, mas NENHUM tem a palavra 'EDITAL' no nome.")

            except Exception as e:
                print(f"   -> Erro ao procurar a tabela de editais: {e}")

            finally:
                # FECHAR ABA E VOLTAR PARA A PESQUISA
                # Independentemente de sucesso ou erro, fecha a aba de detalhes e volta para a principal
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(janela_principal)

        print("\n" + "=" * 50)
        print("✅ PROCESSO TOTAL CONCLUÍDO COM SUCESSO!")
        print("Aguardando 10 segundos para garantir a conclusão dos últimos downloads...")
        time.sleep(10)
        print("=" * 50)

    except Exception as e:
        print(f"Ocorreu um erro crítico durante a execução: {e}")

    finally:
        if 'driver' in locals():
            print("\nEncerrando o navegador.")
            driver.quit()


if __name__ == "__main__":
    extrair_e_baixar_licitacoes()