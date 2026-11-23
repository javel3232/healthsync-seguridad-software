# Contexto de construcción: raíz del proyecto (ver docker-compose.yml).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Usuario sin privilegios y carpeta de archivos subidos (fotos de tarjetas profesionales).
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /var/lib/healthsync/archivos \
    && chown -R app:app /var/lib/healthsync

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# Solo lo que el backend necesita (no el frontend, ni el robot, ni el .env).
COPY backend ./backend
COPY casos ./casos

WORKDIR /app/backend
USER app
EXPOSE 8000

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:create_app()"]
