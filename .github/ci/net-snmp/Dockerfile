FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends snmpd \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /usr/local/bin/net-snmp-agent
RUN chmod 0755 /usr/local/bin/net-snmp-agent

EXPOSE 161/udp

ENTRYPOINT ["/usr/local/bin/net-snmp-agent"]
