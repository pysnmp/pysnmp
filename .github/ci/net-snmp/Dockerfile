# The image carries two agents.
#
# The Debian snmpd package is what the v1, v2c and v3-* profiles run, because it
# is the build real deployments meet. It cannot serve the v3-dh profile: RFC 2786
# lives in the snmp-usm-dh-objects-mib module, which debian/rules does not list
# in MIB_MODULES and which is not in Net-SNMP's default set either, so the
# packaged agent answers noSuchObject for the whole 1.3.6.1.3.101 subtree.
#
# So the DH agent is built from the same source package with that module turned
# on, and installed under /opt where it cannot disturb the packaged one. Only
# the v3-dh profile runs it.
FROM debian:bookworm-slim AS dh-agent

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's/^Types: deb$/Types: deb deb-src/' \
            /etc/apt/sources.list.d/debian.sources; \
    else \
        sed -n 's/^deb \(.*\)$/deb-src \1/p' /etc/apt/sources.list \
            >> /etc/apt/sources.list; \
    fi; \
    apt-get update; \
    # `file` is not a convenience: the libtool configure macro refuses to run
    # without it ("file program not found although it is needed by libtool"),
    # and the slim image does not carry it.
    apt-get install --yes --no-install-recommends \
        ca-certificates dpkg-dev file gcc libc6-dev libssl-dev make; \
    mkdir -p /usr/src/net-snmp; \
    cd /usr/src/net-snmp; \
    apt-get source net-snmp; \
    cd net-snmp-*/; \
    ./configure \
        --quiet \
        --prefix=/opt/net-snmp-dh \
        --with-defaults \
        --with-openssl \
        --with-mib-modules=snmp-usm-dh-objects-mib \
        --without-perl-modules \
        --disable-embedded-perl \
        --disable-manuals; \
    # 5.9.x leaves these two autoconf variables unsubstituted in apps/Makefile,
    # so the link lines hand them to ld as if they were filenames. Neither is
    # needed here -- they belong to the applications, not to the agent.
    sed -i 's/@LIBCRYPTO@/-lcrypto/g; s/@LIBWRAP@//g' apps/Makefile; \
    make -j"$(nproc)"; \
    make install; \
    cd /; \
    rm -rf /usr/src/net-snmp

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends snmpd \
    && rm -rf /var/lib/apt/lists/*

COPY --from=dh-agent /opt/net-snmp-dh /opt/net-snmp-dh

COPY entrypoint.sh /usr/local/bin/net-snmp-agent
RUN chmod 0755 /usr/local/bin/net-snmp-agent

EXPOSE 161/udp
EXPOSE 161/tcp

ENTRYPOINT ["/usr/local/bin/net-snmp-agent"]
