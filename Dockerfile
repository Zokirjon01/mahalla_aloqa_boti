FROM python:3.11-slim

WORKDIR /app

# Tizim paketlarini o'rnatish
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python paketlarini o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kodni nusxalash
COPY . .

# Portni ochish
EXPOSE 8000

# Ishga tushirish
CMD ["python", "bot.py"]