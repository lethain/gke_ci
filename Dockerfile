FROM python:2-alpine3.7 as builder

RUN apk add --update \
    python \
    python-dev \
    py-pip \
    build-base \
  && rm -rf /var/cache/apk/*
RUN pip install virtualenv

WORKDIR /srv
COPY . /srv
RUN virtualenv env
RUN env/bin/pip install -r requirements.txt
RUN env/bin/pip install --upgrade ply

FROM python:2-alpine3.7
COPY --from=builder \
  /srv/ \
  /srv/
