FROM python:3.12-alpine AS builder

RUN apk add --no-cache gcc musl-dev libffi-dev

WORKDIR /app

COPY ./app/requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-alpine

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies from builder
COPY --from=builder /install /usr/local

# 🔹 Copy the entire app directory, including templates/
COPY ./app/ ./

CMD ["python", "billing.svc.py"]

