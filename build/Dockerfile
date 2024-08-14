FROM python:3.8-slim

WORKDIR /app

# Cài đặt các gói hệ thống cần thiết
RUN apt-get update && \
    apt-get install -y gcc libpq-dev && \
    apt-get clean

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "resource_checker.py"]
