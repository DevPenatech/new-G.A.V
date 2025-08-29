# api-negocio/Dockerfile

# 1. Começa com a imagem base do Python
FROM python:3.11-slim

# 2. Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# 3. Copia APENAS o arquivo de dependências primeiro
# (Isso otimiza o cache do Docker)
COPY requirements.txt .

# 4. Roda o pip install para instalar tudo que está no requirements.txt
RUN pip install -r requirements.txt

# 5. Copia todo o resto do código do projeto para o diretório de trabalho
COPY . .

# O comando para rodar a aplicação já está no docker-compose.yml