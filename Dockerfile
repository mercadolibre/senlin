FROM ubuntu:14.04
RUN apt-get update && apt-get -y install git python-pip python-dev build-essential

RUN pip install --upgrade pip && \
  pip install --upgrade virtualenv

# install senlin
RUN mkdir /opt/stack

COPY . /opt/stack/senlin

RUN cd /opt/stack/senlin && \
 pip install -e .


 
