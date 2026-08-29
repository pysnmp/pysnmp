#!/usr/bin/env python
"""Minimal SNMP agent simulator using asyncio backend.

This replaces the old snmpsimd.py from snmpsim 0.4.7 which used the
now-removed pysnmp.carrier.asynsock API. It reads .snmprec data files
and serves them over UDP using the asyncio carrier.
"""

import os
import sys
import getopt
import traceback

from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import cmdrsp, context
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.smi import exval
from pysnmp.proto import rfc1902


def parse_snmprec_line(line):
    """Parse a .snmprec data file line: oid|type|value"""
    parts = line.strip().split('|', 2)
    if len(parts) != 3:
        return None
    oid_str, type_code, value_str = parts
    oid = tuple(int(x) for x in oid_str.split('.'))
    return oid, type_code, value_str


def load_snmprec(data_dir, community):
    """Load .snmprec data file for a given community."""
    data_file = os.path.join(data_dir, community + '.snmprec')
    if not os.path.exists(data_file):
        data_file = os.path.join(data_dir, 'public.snmprec')
    if not os.path.exists(data_file):
        return {}

    records = {}
    with open(data_file) as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            parsed = parse_snmprec_line(line)
            if parsed:
                oid, type_code, value_str = parsed
                records[oid] = (type_code, value_str)
    return records


class SnmprecMibInstrum:
    """Minimal MIB instrument serving records selected by request identity."""

    def __init__(self, data_dir):
        self._data = {
            name: load_snmprec(data_dir, name)
            for name in ('public', 'public@1', '00000', 'testuser')
        }

    @staticmethod
    def _security_name(ac_info):
        """Return the configured security name for the active request."""
        _, snmp_engine = ac_info
        execution_context = snmp_engine.observer.getExecutionContext(
            'rfc3412.receiveMessage:request'
        )
        return str(execution_context['securityName'])

    def _records(self, ac_info):
        return self._data.get(self._security_name(ac_info), self._data['public'])

    def readVars(self, varBinds, acInfo=(None, None)):
        records = self._records(acInfo)
        result = []
        for oid, _ in varBinds:
            oid_tuple = tuple(oid)
            if oid_tuple in records:
                type_code, value_str = records[oid_tuple]
                result.append((oid, self._convert(type_code, value_str)))
            else:
                result.append((oid, exval.endOfMib))
        return result

    def readNextVars(self, varBinds, acInfo=(None, None)):
        records = self._records(acInfo)
        record_oids = sorted(records)
        result = []

        for oid, _ in varBinds:
            oid_tuple = tuple(oid)
            next_oid = next(
                (candidate for candidate in record_oids if candidate > oid_tuple), None
            )
            if next_oid is None:
                result.append((oid, exval.endOfMibView))
            else:
                type_code, value_str = records[next_oid]
                result.append((next_oid, self._convert(type_code, value_str)))

        return result

    def writeVars(self, varBinds, acInfo=(None, None)):
        return [(oid, exval.noSuchInstance) for oid, _ in varBinds]

    def _convert(self, type_code, value_str):
        """Convert string value to ASN.1 type based on type code."""
        if type_code == '4':  # OctetString
            return rfc1902.OctetString(value_str)
        elif type_code == '2':  # Integer32
            return rfc1902.Integer32(int(value_str))
        elif type_code == '6':  # ObjectIdentifier
            return rfc1902.ObjectIdentifier(value_str)
        elif type_code == '3':  # TimeTicks
            return rfc1902.TimeTicks(int(value_str))
        elif type_code == '5':  # Null
            return rfc1902.Null()
        else:
            return rfc1902.OctetString(value_str)


def main():
    """Run the SNMP agent simulator."""
    data_dir = None
    cache_dir = None
    endpoint = '127.0.0.1:1161'
    v3_user = None
    v3_auth_key = None
    v3_auth_proto = None
    v3_priv_key = None
    v3_priv_proto = None
    log_level = 'info'

    try:
        opts, _ = getopt.getopt(
            sys.argv[1:],
            '',
            [
                'data-dir=',
                'cache-dir=',
                'agent-udpv4-endpoint=',
                'v3-user=',
                'v3-auth-key=',
                'v3-auth-proto=',
                'v3-priv-key=',
                'v3-priv-proto=',
                'logging-method=',
                'log-level=',
            ],
        )
    except getopt.GetoptError as e:
        sys.stderr.write(f'Error: {e}\n')
        sys.exit(1)

    for opt, val in opts:
        if opt == '--data-dir':
            data_dir = val
        elif opt == '--cache-dir':
            cache_dir = val
        elif opt == '--agent-udpv4-endpoint':
            endpoint = val
        elif opt == '--v3-user':
            v3_user = val
        elif opt == '--v3-auth-key':
            v3_auth_key = val
        elif opt == '--v3-auth-proto':
            v3_auth_proto = val
        elif opt == '--v3-priv-key':
            v3_priv_key = val
        elif opt == '--v3-priv-proto':
            v3_priv_proto = val
        elif opt == '--log-level':
            log_level = val

    if not data_dir:
        sys.stderr.write('Error: --data-dir is required\n')
        sys.exit(1)

    # Parse endpoint
    host, _, port = endpoint.rpartition(':')
    if not host:
        host = '127.0.0.1'
    port = int(port)

    snmpEngine = engine.SnmpEngine()

    # Set up transport
    config.addTransport(
        snmpEngine, udp.domainName, udp.UdpTransport().openServerMode((host, port))
    )

    # Set up SNMPv1/v2c community
    config.addV1System(snmpEngine, 'public', 'public', securityName='public')
    config.addV1System(snmpEngine, 'public@1', 'public@1', securityName='public@1')

    # Set up SNMPv3 user
    if v3_user:
        auth_protocols = {
            'MD5': config.usmHMACMD5AuthProtocol,
            'SHA': config.usmHMACSHAAuthProtocol,
            'SHA224': config.usmHMAC128SHA224AuthProtocol,
            'SHA256': config.usmHMAC192SHA256AuthProtocol,
            'SHA384': config.usmHMAC256SHA384AuthProtocol,
            'SHA512': config.usmHMAC384SHA512AuthProtocol,
        }
        priv_protocols = {
            'DES': config.usmDESPrivProtocol,
            'AES': config.usmAesCfb128Protocol,
            'AES192': config.usmAesCfb192Protocol,
            'AES192BLMT': config.usmAesBlumenthalCfb192Protocol,
            'AES256': config.usmAesCfb256Protocol,
            'AES256BLMT': config.usmAesBlumenthalCfb256Protocol,
        }
        auth_proto = auth_protocols.get(v3_auth_proto, config.usmNoAuthProtocol)
        priv_proto = priv_protocols.get(v3_priv_proto, config.usmNoPrivProtocol)

        config.addV3User(
            snmpEngine,
            v3_user,
            auth_proto,
            v3_auth_key or None,
            priv_proto,
            v3_priv_key or None,
        )

    # Set up VACM
    config.addVacmUser(snmpEngine, 2, 'public', 'noAuthNoPriv')
    config.addVacmUser(snmpEngine, 2, 'public', 'authNoPriv')
    config.addVacmUser(snmpEngine, 2, '00000', 'noAuthNoPriv')
    config.addVacmUser(snmpEngine, 2, '00000', 'authNoPriv')
    if v3_user:
        config.addVacmUser(snmpEngine, 3, v3_user, 'noAuthNoPriv')
        config.addVacmUser(snmpEngine, 3, v3_user, 'authNoPriv')
        config.addVacmUser(snmpEngine, 3, v3_user, 'authPriv')

    # Set up MIB instrument with .snmprec data
    mibInstrum = SnmprecMibInstrum(data_dir)
    snmpContext = context.SnmpContext(snmpEngine)
    snmpContext.contextNames[b''] = mibInstrum
    for context_name in (b'00000', b'testuser'):
        snmpContext.registerContextName(context_name, mibInstrum)

    # Register command responders
    cmdrsp.GetCommandResponder(snmpEngine, snmpContext)
    cmdrsp.SetCommandResponder(snmpEngine, snmpContext)
    cmdrsp.NextCommandResponder(snmpEngine, snmpContext)
    cmdrsp.BulkCommandResponder(snmpEngine, snmpContext)

    sys.stderr.write(f'Listening at UDP/IPv4 endpoint {host}:{port}\n')
    sys.stderr.flush()

    snmpEngine.transportDispatcher.runDispatcher()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        traceback.print_exc()
        sys.exit(1)
