FROM python:3.9
EXPOSE 8002
ENV WSGI_CONF /etc/apache2/sites-available/000-default.conf
WORKDIR /var/www

RUN pip install --upgrade awscli

# Install Dependencies
RUN apt-get update \
     && apt-get install -y --no-install-recommends default-libmysqlclient-dev gcc unzip cron apache2 python3-dev libapache2-mod-wsgi-py3 libsasl2-dev \
     libldap2-dev libssl-dev libcurl4-openssl-dev libbz2-dev \
     && rm -rf /var/lib/apt/lists/*

RUN ln -sf /dev/stdout /var/log/apache2/access.log
RUN ln -sf /dev/stderr /var/log/apache2/error.log

# RUN pip install awscli
RUN pip install --extra-index https://pypi.swarm.devfactory.com/simple/ iws-logging

ADD requirements.txt .
#RUN pip install --upgrade pip
RUN pip install py2neo
RUN pip install -r requirements.txt

ADD . .
RUN python manage.py collectstatic --noinput
COPY ./apache-conf.conf ${WSGI_CONF}
RUN chmod +x run.sh
RUN chmod -R 757 /var/www
#RUN python manage.py migrate
CMD ./run.sh
