FROM python:3.9.6

WORKDIR /app

RUN apt-get update

ADD requirements.txt .
RUN python -m pip install -r requirements.txt 

ADD src .

CMD [ "./run.sh" ]