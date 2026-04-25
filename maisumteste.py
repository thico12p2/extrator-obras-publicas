from selenium import webdriver
import time

print("1. Iniciando o motor do Chrome (Sem opções)...")
try:
    driver = webdriver.Chrome()
    print("✅ Chrome abriu com sucesso!")

    print("2. Tentando acessar o Google...")
    driver.get("https://www.google.com")
    time.sleep(2)
    print("✅ Google acessado!")

    print("3. Tentando acessar a Prefeitura de Macaé...")
    driver.get("https://transparencia.macae.rj.gov.br/contratacoes/contratos")
    time.sleep(2)
    print("✅ Macaé acessado!")

    driver.quit()
    print("\n🎉 TUDO VERDE! O seu Selenium está funcionando perfeitamente.")
    print("O erro estava na configuração da pasta de downloads no código principal.")

except Exception as e:
    print(f"\n❌ O ERRO ACONTECEU AQUI: {e}")
    try:
        driver.quit()
    except:
        pass