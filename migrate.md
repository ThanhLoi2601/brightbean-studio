python manage.py migrate
python manage.py makemigrations

python manage.py makemigrations analytics
python manage.py migrate

-- test
python manage.py collect_analytics --type full

-- Start background worker
python manage.py process_tasks