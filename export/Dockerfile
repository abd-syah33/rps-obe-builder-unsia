# Layanan ekspor RPS Builder v2. Build dari AKAR repo:
#   docker build -f export/Dockerfile -t rps-ekspor .
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-writer-nogui fonts-liberation fonts-crosextra-carlito fonts-crosextra-caladea fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 10001 ekspor
WORKDIR /app
COPY export/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY docx_export.py pdf_export.py ./
COPY assets/ ./assets/
COPY export/app.py ./
USER ekspor
ENV HOME=/home/ekspor EKSPOR_CACHE=/home/ekspor/cache
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/sehat')"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
