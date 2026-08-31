#!/bin/sh
set -eu

: "${SNMP_PROFILE:?SNMP_PROFILE is required}"

cat > /etc/snmp/snmpd.conf <<EOF
agentAddress udp:161
sysLocation PySNMP CI Net-SNMP agent
sysContact pysnmp-ci@example.invalid
sysName pysnmp-ci-${SNMP_PROFILE}
dontLogTCPWrappersConnects yes
EOF

case "${SNMP_PROFILE}" in
  v1)
    echo 'rocommunity ci-v1-community default .1' >> /etc/snmp/snmpd.conf
    ;;
  v2c)
    echo 'rocommunity ci-v2c-community default .1' >> /etc/snmp/snmpd.conf
    ;;
  v3-noauth)
    echo 'createUser ci-noauth' > /var/lib/snmp/snmpd.conf
    echo 'rouser ci-noauth noauth .1' >> /etc/snmp/snmpd.conf
    ;;
  v3-sha)
    echo 'createUser ci-sha SHA ciAuthPass123' > /var/lib/snmp/snmpd.conf
    echo 'rouser ci-sha auth .1' >> /etc/snmp/snmpd.conf
    ;;
  v3-aes)
    echo 'createUser ci-aes SHA ciAuthPass123 AES ciPrivPass123' > /var/lib/snmp/snmpd.conf
    echo 'rouser ci-aes priv .1' >> /etc/snmp/snmpd.conf
    ;;
  v3-des)
    echo 'createUser ci-des SHA ciAuthPass123 DES ciPrivPass123' > /var/lib/snmp/snmpd.conf
    echo 'rouser ci-des priv .1' >> /etc/snmp/snmpd.conf
    ;;
  *)
    echo "Unsupported SNMP_PROFILE: ${SNMP_PROFILE}" >&2
    exit 2
    ;;
esac

chown -R Debian-snmp:Debian-snmp /var/lib/snmp
exec snmpd -f -Lo
