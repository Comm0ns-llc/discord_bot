FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# Install git (sometimes needed for dependencies)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create logs directory
RUN mkdir -p logs

CMD ["python", "main.py"]
