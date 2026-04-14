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
            
            # ... SEU CÓDIGO DE PAGINAÇÃO VEM AQUI ...