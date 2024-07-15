# Usar imagem base do Python
FROM python:3.9-slim

# Instalar git
RUN apt-get update && apt-get install -y git

# Definir o diretório de trabalho
WORKDIR /app

# Copiar o arquivo requirements.txt
COPY requirements.txt .

# Instalar as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o restante do código da aplicação
COPY . .

# Expor a porta que a aplicação vai rodar
EXPOSE 5000

# Comando para rodar a aplicação
CMD ["python", "app.py"]
