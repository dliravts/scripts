FROM python:3.10.0-alpine3.14

WORKDIR /app

# Instala dependencias necesarias
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY wasabi-exporter.py .

EXPOSE 9150

CMD ["python", "wasabi-exporter.py"]
