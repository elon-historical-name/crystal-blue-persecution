FROM python:alpine3.18

WORKDIR /usr/src/app

RUN apk add --no-cache --update \
    chromium-chromedriver

COPY . .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "./main.py"]