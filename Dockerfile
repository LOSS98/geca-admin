FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

dockerfile# Ajoutez ces packages
RUN pip install --no-cache-dir gevent

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--worker-class", "gevent", "--worker-connections", "1000", "--timeout", "300", "--log-level", "info", "wsgi:app"]
