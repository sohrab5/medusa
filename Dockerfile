FROM alpine:3.20

ARG NGINX_CONFS_DIR
ARG WEBROOT_DIR

EXPOSE 80

RUN apk update && apk add --no-cache nginx

COPY ${WEBROOT_DIR}/ /var/www/webroot/

RUN rm -f /etc/nginx/http.d/*

COPY ${NGINX_CONFS_DIR}/* /etc/nginx/http.d/

COPY nginx.conf /etc/nginx/nginx.conf

ENTRYPOINT ["nginx"]

