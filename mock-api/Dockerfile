FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd --create-home --uid 10002 mock
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
USER mock
EXPOSE 9000
CMD ["gunicorn", "--bind", "0.0.0.0:9000", "--workers", "2", "--threads", "4", "--access-logfile", "-", "app:app"]
