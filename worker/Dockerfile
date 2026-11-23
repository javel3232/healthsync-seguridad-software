FROM debian:trixie-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ make libcurl4-openssl-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10003 --no-create-home robot
WORKDIR /src
COPY Makefile ./
COPY src ./src
RUN make
USER robot
# ROBOT=validacion | alertas se define en docker-compose.yml (un servicio por robot).
CMD ["/src/robot"]
