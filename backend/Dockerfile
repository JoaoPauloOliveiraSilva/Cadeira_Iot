# 1. Usar uma imagem oficial do Python (versão "slim" para ser mais leve)
FROM python:3.10-slim

# 2. Definir a pasta de trabalho lá dentro
WORKDIR /app

# 3. Copiar o ficheiro de dependências e instalá-las
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copiar o código da tua API (a pasta app) para dentro do contentor
COPY ./app ./app

# 5. Dizer ao Docker que o contentor vai falar pela porta 8000
EXPOSE 8000

# 6. O comando de arranque (exatamente o que fazias no terminal, mas sem o --reload)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]