FROM python:3.11

ENV PYTHONUNBUFFERED=1

RUN apt update && \
    apt install -y wget gnupg tini && \
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt update && \
    apt install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

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

ENTRYPOINT ["/usr/bin/tini", "--", "/scripts/run-bot.sh"]
