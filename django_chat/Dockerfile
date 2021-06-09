FROM python:3.9-alpine

WORKDIR /usr/src/app

COPY freeze.txt ./
RUN pip install --no-cache-dir -r freeze.txt

COPY . .

RUN python manage.py collectstatic --no-input
RUN python manage.py makemigrations
RUN python manage.py migrate

EXPOSE 8000
CMD [ "gunicorn", "--chdir", "/usr/src/app/", "--bind", "0.0.0.0:8000", "j95io.wsgi:application" ]


