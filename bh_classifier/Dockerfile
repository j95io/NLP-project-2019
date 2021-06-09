FROM python:3.9

WORKDIR /usr/src/app

COPY freeze.txt ./
RUN pip install --no-cache-dir -r freeze.txt

COPY . .

EXPOSE 18861
CMD [ "python", "./classifier.py" ]

