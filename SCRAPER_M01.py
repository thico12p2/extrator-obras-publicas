import requests
from bs4 import BeautifulSoup
import pandas as pd

def extrair_citacoes():
    print("Iniciando o scraper de teste...")
    
    # Site seguro e legalizado para testes de scraping
    url = "http://quotes.toscrape.com/"
    resposta = requests.get(url)
    
    # Analisa o HTML da página
    soup = BeautifulSoup(resposta.text, "html.parser")
    
    dados_extraidos = []
    
    # Encontra todos os blocos que contêm as citações
    blocos_citacao = soup.find_all("div", class_="quote")
    
    for bloco in blocos_citacao:
        texto = bloco.find("span", class_="text").text
        autor = bloco.find("small", class_="author").text
        
        dados_extraidos.append({
            "Autor": autor,
            "Citação": texto
        })
        
    # Transforma em uma tabela e salva em CSV
    df = pd.DataFrame(dados_extraidos)
    df.to_csv("dados_teste.csv", index=False)
    
    print(f"Sucesso! {len(df)} citações foram salvas no arquivo 'dados_teste.csv'.")

if __name__ == "__main__":
    extrair_citacoes()