
FROM selenium/standalone-chrome

# TODO: try to remove root user
USER root

RUN apt-get update && apt-get install -y software-properties-common git
RUN add-apt-repository -y ppa:deadsnakes/ppa
RUN apt-get update && apt-get install -y python3.11 postgresql-client

RUN wget https://github.com/golang-migrate/migrate/releases/download/v4.15.2/migrate.linux-amd64.tar.gz && \
    tar zxvf migrate.linux-amd64.tar.gz && \
    mv migrate /usr/local/bin/go-migrate && \
    chmod u+x /usr/local/bin/go-migrate && \
    rm migrate.linux-amd64.tar.gz

ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN wget https://bootstrap.pypa.io/get-pip.py
RUN python3.11 get-pip.py
RUN python3.11 -m pip install -U pip setuptools
RUN python3.11 -m pip install -r requirements.txt

COPY scripts /scripts
RUN chmod u+x /scripts/*

COPY . /srv/root
WORKDIR /srv/root

EXPOSE 80

ENTRYPOINT [ "/scripts/run-bot.sh" ]
