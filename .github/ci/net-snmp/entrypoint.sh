#!/bin/sh
set -eu

: "${SNMP_PROFILE:?SNMP_PROFILE is required}"

# The v3-dh profile is the odd one out: RFC 2786 needs the agent built with
# snmp-usm-dh-objects-mib, which the Debian package is not, so this profile runs
# the agent installed under /opt instead. Two users, because the key change is
# destructive -- ci-dh is the one the tests rotate, and ci-dh-static stays on its
# original passphrase so read-only checks do not depend on rotation order.
if [ "${SNMP_PROFILE}" = "v3-dh" ]; then
  DH_PREFIX=/opt/net-snmp-dh
  mkdir -p "${DH_PREFIX}/var"
  cat > "${DH_PREFIX}/snmpd.conf" <<EOF
agentAddress udp:161
sysContact pysnmp-ci@example.invalid
sysName pysnmp-ci-${SNMP_PROFILE}
dontLogTCPWrappersConnects yes
createUser ci-dh SHA ciAuthPass123
createUser ci-dh-static SHA ciAuthPass123
rwuser ci-dh auth .1
rouser ci-dh-static auth .1
EOF
  exec "${DH_PREFIX}/sbin/snmpd" -f -Lo -C -c "${DH_PREFIX}/snmpd.conf" \
    --persistentDir="${DH_PREFIX}/var"
fi

cat > /etc/snmp/snmpd.conf <<EOF
agentAddress udp:161
# Note: sysLocation is intentionally NOT set here. A sysLocation directive
# marks sysLocation.0 read-only in snmpd; leaving it unset keeps sysLocation.0
# writable (default "Unknown") so the SET roundtrip test can exercise it.
sysContact pysnmp-ci@example.invalid
sysName pysnmp-ci-${SNMP_PROFILE}
dontLogTCPWrappersConnects yes
EOF

case "${SNMP_PROFILE}" in
  v1)
    echo 'rwcommunity ci-v1-community default .1' >> /etc/snmp/snmpd.conf
    ;;
  v2c)
    echo 'rwcommunity ci-v2c-community default .1' >> /etc/snmp/snmpd.conf
    ;;
  v3-noauth)
    echo 'createUser ci-noauth' > /var/lib/snmp/snmpd.conf
    echo 'rwuser ci-noauth noauth .1' >> /etc/snmp/snmpd.conf
    ;;
  v3-sha)
    echo 'createUser ci-sha SHA ciAuthPass123' > /var/lib/snmp/snmpd.conf
    echo 'rwuser ci-sha auth .1' >> /etc/snmp/snmpd.conf
    ;;
  v3-aes)
    echo 'createUser ci-aes SHA ciAuthPass123 AES ciPrivPass123' > /var/lib/snmp/snmpd.conf
    echo 'rwuser ci-aes priv .1' >> /etc/snmp/snmpd.conf
    ;;
  v3-des)
    echo 'createUser ci-des SHA ciAuthPass123 DES ciPrivPass123' > /var/lib/snmp/snmpd.conf
    echo 'rwuser ci-des priv .1' >> /etc/snmp/snmpd.conf
    ;;
  *)
    echo "Unsupported SNMP_PROFILE: ${SNMP_PROFILE}" >&2
    exit 2
    ;;
esac

chown -R Debian-snmp:Debian-snmp /var/lib/snmp
exec snmpd -f -Lo
