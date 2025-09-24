# Imagem base Python
FROM python:3.12-slim

# Diretório de trabalho dentro do container
WORKDIR /app

# Copia o requirements.txt e instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código
COPY . .

# Variáveis de ambiente (opcional, podem ser substituídas no docker run)
ENV MONGO_URI="mongodb://facetecadmin:strongpassword@172.16.1.4:27017/facetec-sdk-data?authSource=admin"
ENV MONGO_DB_NAME="facetec-sdk-data"
ENV MONGO_COLLECTION="Session"
ENV FACETEC_SIGNATURE_SECRET="minhaassinaturasecreta"
ENV PORT=3333

# Expõe a porta que o FastAPI vai rodar
EXPOSE 3333

# Comando para rodar a aplicação
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3333"]
