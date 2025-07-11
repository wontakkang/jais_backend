# DJANGO
python manage.py makemigrations
python manage.py migrate
python manage.py 192.168.0.63:8000

# FAST API
uvicorn main:app --reload --host 192.168.0.63 --port 8000 -- reload
