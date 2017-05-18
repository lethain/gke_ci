FROM ubuntu:zesty

RUN apt-key update
RUN apt-get update
RUN apt-get remove apt-listchanges
RUN apt-get install python-dev -y
RUN apt-get install python-pip -y
COPY . /
RUN pip install -r requirements.txt
RUN pip install --upgrade ply
