FROM python:3.13-slim

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY sap-o2c-data/ /app/sap-o2c-data/

RUN chmod +x /app/backend/start.sh

CMD ["/app/backend/start.sh"]
