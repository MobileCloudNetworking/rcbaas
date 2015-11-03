FROM gliderlabs/alpine:3.1

WORKDIR /app
COPY . /app
RUN apk --update add --virtual build-dependencies \
    python-dev \
    py-pip \
    build-base \
    curl \
    && pip install virtualenv \
    && virtualenv /env \
	&& curl -s -k -o /tmp/sdk.tar.gz 'https://owncloud.mobile-cloud-networking.eu/owncloud/public.php?service=files&t=01ad0519e7e4ad9bc8fdbf5f959f183e&download' \
	&& /env/bin/pip install /tmp/sdk.tar.gz \
	&& curl -s -k -o /tmp/sm.tar.gz 'https://owncloud.mobile-cloud-networking.eu/owncloud/public.php?service=files&t=3ec7178ae3587866a0d94e27af95024b&download' \
	&& /env/bin/pip install /tmp/sm.tar.gz \
	&& /env/bin/pip install -r /app/requirements.txt \
	&& /env/bin/python setup.py install \
	&& rm -rf /var/cache/apk/* /root/.cache/*
EXPOSE 8080
CMD ["/env/bin/python", "./wsgi/application"]