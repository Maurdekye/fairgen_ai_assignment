FROM python:3.9.6

RUN apt-get update

# install pip packages
RUN python -m pip update
RUN python -m pip install fastapi 
RUN python -m pip install "uvicorn[standard]"
RUN python -m pip install simplejsondb
RUN python -m pip install "python-jose[cryptography]"
RUN python -m pip install "passlib[bcrypt]"
RUN python -m pip install python-multipart

CMD [ "./run.sh" ]