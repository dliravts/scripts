FROM python:3.10.0-alpine3.14

WORKDIR /app

# Instala dependencias necesarias
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY webhook.py config.ini ./

EXPOSE 5000

CMD ["python", "webhook.py"]
