FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY sincronizador.py ./
CMD ["python", "-u", "sincronizador.py"]
