FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir -r Requirements.txt gunicorn

EXPOSE 8000

CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8000", "--timeout", "120", "--access-logfile", "-", "example.NepseServer:app"]
