FROM mobilecloudnetworking/mcn_so_base_ops

WORKDIR /app

COPY . /app

EXPOSE 8080
CMD ["/env/bin/python", "./wsgi/application"]