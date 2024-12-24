FROM python:3.11

ENV PYTHONUNBUFFERED=1

RUN wget http://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_127.0.6533.72-1_amd64.deb
RUN apt update && \
    apt install ./google-chrome-stable_127.0.6533.72-1_amd64.deb -y && \
    rm google-chrome-stable_127.0.6533.72-1_amd64.deb

COPY requirements.txt .
RUN pip install -U pip setuptools
RUN pip install -r requirements.txt
RUN pip install git+https://github.com/osuAkatsuki/akatsuki-cli

RUN apt update && \
    apt install -y postgresql-client

RUN wget https://github.com/golang-migrate/migrate/releases/download/v4.15.2/migrate.linux-amd64.tar.gz && \
    tar zxvf migrate.linux-amd64.tar.gz && \
    mv migrate /usr/local/bin/go-migrate && \
    chmod u+x /usr/local/bin/go-migrate && \
    rm migrate.linux-amd64.tar.gz

COPY scripts /scripts
RUN chmod u+x /scripts/*

COPY . /srv/root
WORKDIR /srv/root

ENTRYPOINT ["/scripts/run-bot.sh"]
