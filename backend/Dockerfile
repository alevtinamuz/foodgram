FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir

COPY . .

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && mkdir -p /backend_static/static && cp -r /app/collected_static/. /backend_static/static/ && python manage.py load_ingredients && python manage.py load_test_data && gunicorn --bind 0.0.0.0:8000 foodgram_backend.wsgi"]