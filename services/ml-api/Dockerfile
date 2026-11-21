FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY services/ml-api/requirements.txt /app/services/ml-api/requirements.txt
RUN pip install --no-cache-dir -r /app/services/ml-api/requirements.txt

COPY pipeline/__init__.py /app/pipeline/__init__.py
COPY pipeline/ml/__init__.py /app/pipeline/ml/__init__.py
COPY pipeline/ml/features.py /app/pipeline/ml/features.py
COPY services/ml-api /app/services/ml-api
COPY models /app/models

ENV PYTHONPATH=/app \
    MODEL_PATH=models/salary_champion.joblib \
    FEATURE_SPEC_PATH=models/feature_spec.json \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --app-dir /app/services/ml-api --host 0.0.0.0 --port ${PORT:-8000}"]
