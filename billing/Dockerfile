FROM python:3.12-alpine AS builder

RUN apk add --no-cache gcc musl-dev libffi-dev

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-alpine

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /install /usr/local

COPY billing.svc.py .

CMD ["python", "billing.svc.py"]
