FROM python:3.11.6-alpine3.18

WORKDIR /usr/src/app

RUN apk add --no-cache --update \
    chromium-chromedriver

COPY . .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "./main.py"]