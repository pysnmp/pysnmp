"""Tests for RFC 3413 section 6 notification filtering."""

# ruff: noqa: I001 -- SnmpEngine must load before entity.config to avoid the
# security-model package's import cycle during isolated test collection.

from pyasn1.type.univ import Integer, ObjectIdentifier, OctetString

from pysnmp.entity.engine import SnmpEngine
from pysnmp.entity import config
from pysnmp.entity.rfc3413 import config as lcd_config
from pysnmp.entity.rfc3413 import ntforg
from pysnmp.proto import errind, error
from pysnmp.proto.api import v2c


SNMP_TRAP_OID = (1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0)
COLD_START = (1, 3, 6, 1, 6, 3, 1, 1, 5, 1)
SYS_DESCR = (1, 3, 6, 1, 2, 1, 1, 1, 0)
SYS_OBJECT_ID = (1, 3, 6, 1, 2, 1, 1, 2, 0)


def _filter_entry(subtree, mask=b'', filter_type=1):
    return ObjectIdentifier(subtree), OctetString(mask), Integer(filter_type)


def _setup_lcd(filter_subtree=None, filter_type='included'):
    engine = SnmpEngine()
    config.addTargetParams(engine, 'params', 'security-name', 'noAuthNoPriv', 1)

    options = {}
    if filter_subtree is not None:
        options.update(
            filterSubtree=filter_subtree,
            filterMask=b'',
            filterType=filter_type,
        )

    config.addNotificationTarget(engine, 'notification', 'params', 'tag', 'trap', **options)
    return engine


def _add_filter(engine, profile_name, subtree, filter_type='included'):
    mib_builder = engine.msgAndPduDsp.mibInstrumController.mibBuilder
    (entry,) = mib_builder.importSymbols('SNMP-NOTIFICATION-MIB', 'snmpNotifyFilterEntry')
    instance_id = entry.getInstIdFromIndices(profile_name, subtree)
    engine.msgAndPduDsp.mibInstrumController.writeVars(
        (
            (entry.name + (5,) + instance_id, 'destroy'),
            (entry.name + (1,) + instance_id, subtree),
            (entry.name + (2,) + instance_id, b''),
            (entry.name + (3,) + instance_id, filter_type),
            (entry.name + (5,) + instance_id, 'createAndGo'),
        )
    )
    return instance_id


def _patch_originator_config(monkeypatch, targets, profiles=None, filters=None, notify_type=1):
    profiles = profiles or {}
    filters = filters or {}

    monkeypatch.setattr(ntforg.config, 'getNotificationInfo', lambda *args: ('tag', notify_type))
    monkeypatch.setattr(ntforg.config, 'getTargetNames', lambda *args: list(targets))
    monkeypatch.setattr(
        ntforg.config,
        'getTargetAddr',
        lambda engine, target: ((1, 3, 6), ('127.0.0.1', 162), 100, 0, target),
    )
    monkeypatch.setattr(
        ntforg.config,
        'getTargetParams',
        lambda engine, params: (1, 2, params, 1),
    )
    monkeypatch.setattr(
        ntforg.config,
        'getNotifyFilterProfile',
        lambda engine, params: profiles.get(params),
    )
    monkeypatch.setattr(
        ntforg.config,
        'getNotifyFilter',
        lambda engine, profile: filters.get(profile, []),
    )


def _notification_var_binds(*object_names):
    var_binds = [(SNMP_TRAP_OID, ObjectIdentifier(COLD_START))]
    var_binds.extend((name, OctetString('value')) for name in object_names)
    return var_binds


def _capture_sends(monkeypatch, originator):
    sent = []

    def send_pdu(*args):
        target, pdu = args[1], args[4]
        sent.append((target, v2c.apiPDU.getVarBinds(pdu)))
        return len(sent)

    monkeypatch.setattr(originator, 'sendPdu', send_pdu)
    return sent


class TestMatchFilter:
    def test_no_match_is_distinct_from_included(self):
        entries = [_filter_entry((1, 3, 6, 1, 2, 1), filter_type=1)]
        assert ntforg._matchFilter(entries, ObjectIdentifier(COLD_START)) is None

    def test_empty_profile_has_no_match(self):
        assert ntforg._matchFilter([], ObjectIdentifier(COLD_START)) is None

    def test_included_and_excluded_matches(self):
        oid = ObjectIdentifier(SYS_DESCR)
        assert ntforg._matchFilter([_filter_entry((1, 3, 6), filter_type=1)], oid) is True
        assert ntforg._matchFilter([_filter_entry((1, 3, 6), filter_type=2)], oid) is False

    def test_longest_match_wins_independent_of_input_order(self):
        entries = [
            _filter_entry((1, 3, 6, 1, 2, 1, 1), filter_type=2),
            _filter_entry((1, 3, 6), filter_type=1),
        ]
        assert ntforg._matchFilter(entries, ObjectIdentifier(SYS_DESCR)) is False
        assert ntforg._matchFilter(list(reversed(entries)), ObjectIdentifier(SYS_DESCR)) is False

    def test_equal_length_tie_uses_original_subtree(self):
        entries = [
            _filter_entry((9, 3), mask=b'\x40', filter_type=1),
            _filter_entry((1, 9), mask=b'\x80', filter_type=2),
        ]
        assert ntforg._matchFilter(entries, ObjectIdentifier((1, 3))) is True

    def test_mask_is_msb_first_and_missing_bits_are_exact(self):
        entry = _filter_entry((1, 3, 6, 1, 2, 1, 1, 1, 0), mask=b'\x00', filter_type=2)
        assert ntforg._matchFilter([entry], ObjectIdentifier(SYS_DESCR)) is False
        different_ninth_sub_id = ObjectIdentifier((9, 9, 9, 9, 9, 9, 9, 9, 1))
        assert ntforg._matchFilter([entry], different_ninth_sub_id) is None

    def test_oid_shorter_than_subtree_does_not_match(self):
        entry = _filter_entry((1, 3, 6), mask=b'\x00', filter_type=2)
        assert ntforg._matchFilter([entry], ObjectIdentifier((1, 3))) is None


class TestFilterReaders:
    def test_explicit_profile_name_supports_shared_target_params(self):
        engine = SnmpEngine()
        config.addTargetParams(engine, 'params', 'security-name', 'noAuthNoPriv', 1)
        config.addNotificationTarget(
            engine,
            'first-notification',
            'params',
            'tag',
            'trap',
            filterSubtree=COLD_START,
            filterMask=b'',
            filterType='included',
            filterProfileName='shared-profile',
        )
        config.addNotificationTarget(
            engine,
            'second-notification',
            'params',
            'tag',
            'trap',
            filterSubtree=SYS_DESCR,
            filterMask=b'',
            filterType='excluded',
            filterProfileName='shared-profile',
        )

        profile = lcd_config.getNotifyFilterProfile(engine, 'params')
        assert profile == OctetString('shared-profile')
        assert {tuple(entry[0]) for entry in lcd_config.getNotifyFilter(engine, profile)} == {
            COLD_START,
            SYS_DESCR,
        }

    def test_decodes_composite_index_and_returns_active_row(self):
        engine = _setup_lcd(COLD_START)
        profile = lcd_config.getNotifyFilterProfile(engine, 'params')
        filters = lcd_config.getNotifyFilter(engine, profile)
        assert len(filters) == 1
        assert tuple(filters[0][0]) == COLD_START

    def test_profile_names_with_common_prefix_do_not_cross_match(self):
        engine = _setup_lcd()
        _add_filter(engine, 'profile', COLD_START)
        _add_filter(engine, 'profile-extra', SYS_DESCR, 'excluded')
        first = lcd_config.getNotifyFilter(engine, OctetString('profile'))
        second = lcd_config.getNotifyFilter(engine, OctetString('profile-extra'))
        assert [tuple(entry[0]) for entry in first] == [COLD_START]
        assert [tuple(entry[0]) for entry in second] == [SYS_DESCR]

    def test_inactive_profile_is_ignored(self):
        engine = _setup_lcd(COLD_START)
        mib_builder = engine.msgAndPduDsp.mibInstrumController.mibBuilder
        (entry, row_status) = mib_builder.importSymbols(
            'SNMP-NOTIFICATION-MIB',
            'snmpNotifyFilterProfileEntry',
            'snmpNotifyFilterProfileRowStatus',
        )
        instance_id = entry.getInstIdFromIndices('params')
        status_node = row_status.getNode(row_status.name + instance_id)
        status_node.syntax = status_node.syntax.clone('notInService')
        assert lcd_config.getNotifyFilterProfile(engine, 'params') is None

    def test_inactive_filter_row_is_ignored(self):
        engine = _setup_lcd(COLD_START)
        profile = lcd_config.getNotifyFilterProfile(engine, 'params')
        mib_builder = engine.msgAndPduDsp.mibInstrumController.mibBuilder
        (entry, row_status) = mib_builder.importSymbols(
            'SNMP-NOTIFICATION-MIB',
            'snmpNotifyFilterEntry',
            'snmpNotifyFilterRowStatus',
        )
        instance_id = entry.getInstIdFromIndices(profile, COLD_START)
        status_node = row_status.getNode(row_status.name + instance_id)
        status_node.syntax = status_node.syntax.clone('notInService')
        assert lcd_config.getNotifyFilter(engine, profile) == []

    def test_filter_cache_invalidates_without_manual_reset(self):
        engine = _setup_lcd(COLD_START)
        profile = lcd_config.getNotifyFilterProfile(engine, 'params')
        assert len(lcd_config.getNotifyFilter(engine, profile)) == 1
        _add_filter(engine, profile, SYS_DESCR, 'excluded')
        assert len(lcd_config.getNotifyFilter(engine, profile)) == 2


class TestNotificationOriginatorFiltering:
    def test_filtering_is_applied_independently_per_target(self, monkeypatch):
        engine = SnmpEngine()
        _patch_originator_config(
            monkeypatch,
            ['filtered', 'unfiltered'],
            profiles={'filtered': 'profile'},
            filters={'profile': [_filter_entry((1, 3, 6, 1, 2, 1), filter_type=1)]},
        )
        monkeypatch.setattr(engine.accessControlModel[3], 'isAccessAllowed', lambda *args: None)
        originator = ntforg.NotificationOriginator()
        sent = _capture_sends(monkeypatch, originator)

        originator.sendVarBinds(
            engine, 'notification', None, '', _notification_var_binds(SYS_DESCR)
        )
        assert [target for target, _ in sent] == ['unfiltered']

    def test_no_profile_sends_all_var_binds_unchanged(self, monkeypatch):
        engine = SnmpEngine()
        _patch_originator_config(monkeypatch, ['target'])
        monkeypatch.setattr(engine.accessControlModel[3], 'isAccessAllowed', lambda *args: None)
        originator = ntforg.NotificationOriginator()
        sent = _capture_sends(monkeypatch, originator)
        originator.sendVarBinds(
            engine, 'notification', None, '', _notification_var_binds(SYS_DESCR)
        )
        assert len(sent) == 1
        assert [tuple(name) for name, _ in sent[0][1]][2:] == [SYS_DESCR]

    def test_notification_name_must_be_specifically_included(self, monkeypatch):
        engine = SnmpEngine()
        _patch_originator_config(
            monkeypatch,
            ['target'],
            profiles={'target': 'profile'},
            filters={'profile': [_filter_entry((1, 3, 6, 1, 2, 1), filter_type=1)]},
        )
        monkeypatch.setattr(engine.accessControlModel[3], 'isAccessAllowed', lambda *args: None)
        originator = ntforg.NotificationOriginator()
        sent = _capture_sends(monkeypatch, originator)
        originator.sendVarBinds(
            engine, 'notification', None, '', _notification_var_binds(SYS_DESCR)
        )
        assert not sent

    def test_excluded_object_suppresses_whole_notification(self, monkeypatch):
        engine = SnmpEngine()
        filters = {
            'profile': [
                _filter_entry(COLD_START, filter_type=1),
                _filter_entry(SYS_DESCR, filter_type=2),
            ]
        }
        _patch_originator_config(
            monkeypatch, ['target'], profiles={'target': 'profile'}, filters=filters
        )
        monkeypatch.setattr(engine.accessControlModel[3], 'isAccessAllowed', lambda *args: None)
        originator = ntforg.NotificationOriginator()
        sent = _capture_sends(monkeypatch, originator)
        originator.sendVarBinds(
            engine,
            'notification',
            None,
            '',
            _notification_var_binds(SYS_DESCR, SYS_OBJECT_ID),
        )
        assert not sent

    def test_mandatory_only_notification_is_valid(self, monkeypatch):
        engine = SnmpEngine()
        _patch_originator_config(
            monkeypatch,
            ['target'],
            profiles={'target': 'profile'},
            filters={'profile': [_filter_entry(COLD_START, filter_type=1)]},
        )
        monkeypatch.setattr(engine.accessControlModel[3], 'isAccessAllowed', lambda *args: None)
        originator = ntforg.NotificationOriginator()
        sent = _capture_sends(monkeypatch, originator)
        originator.sendVarBinds(engine, 'notification', None, '', _notification_var_binds())
        assert len(sent) == 1
        assert len(sent[0][1]) == 2

    def test_vacm_checks_notification_oid_value(self, monkeypatch):
        engine = SnmpEngine()
        _patch_originator_config(monkeypatch, ['target'])

        def deny_notification_oid(*args):
            variable_name = args[-1]
            if tuple(variable_name) == COLD_START:
                raise error.StatusInformation(errorIndication=errind.notInView)

        monkeypatch.setattr(engine.accessControlModel[3], 'isAccessAllowed', deny_notification_oid)
        originator = ntforg.NotificationOriginator()
        sent = _capture_sends(monkeypatch, originator)
        originator.sendVarBinds(
            engine, 'notification', None, '', _notification_var_binds(SYS_DESCR)
        )
        assert not sent

    def test_vacm_denial_only_skips_affected_target(self, monkeypatch):
        engine = SnmpEngine()
        _patch_originator_config(monkeypatch, ['denied', 'allowed'])

        def target_access(*args):
            security_name = args[2]
            if security_name == 'denied':
                raise error.StatusInformation(errorIndication=errind.notInView)

        monkeypatch.setattr(engine.accessControlModel[3], 'isAccessAllowed', target_access)
        originator = ntforg.NotificationOriginator()
        sent = _capture_sends(monkeypatch, originator)
        originator.sendVarBinds(
            engine, 'notification', None, '', _notification_var_binds(SYS_DESCR)
        )
        assert [target for target, _ in sent] == ['allowed']

    def test_filtered_inform_completes_callback(self, monkeypatch):
        engine = SnmpEngine()
        _patch_originator_config(
            monkeypatch,
            ['target'],
            profiles={'target': 'profile'},
            filters={'profile': [_filter_entry((1, 3, 6, 1, 2, 1), filter_type=1)]},
            notify_type=2,
        )
        monkeypatch.setattr(engine.accessControlModel[3], 'isAccessAllowed', lambda *args: None)
        originator = ntforg.NotificationOriginator()
        sent = _capture_sends(monkeypatch, originator)
        callbacks = []

        def callback(*args):
            callbacks.append(args)

        originator.sendVarBinds(
            engine,
            'notification',
            None,
            '',
            _notification_var_binds(SYS_DESCR),
            callback,
        )
        assert not sent
        assert len(callbacks) == 1
        assert callbacks[0][2:6] == (None, 0, 0, ())
        assert originator._NotificationOriginator__pendingNotifications == {}
