# pysnmp activates a row in these tables before it has the secrets to put in
# it: pysnmp/entity/config.py writes pysnmpUsmSecretStatus 'createAndGo' first
# and the key columns after. MibTableRow.writeCommit checks, at the moment a
# row goes active, that every non-optional column in it holds a value, so the
# columns have to hold something by the time the RowStatus commits.
#
# The MIB says nothing about this. There is no DEFVAL clause on any of these
# objects -- the ordering is pysnmp's, and so is the placeholder. Both key
# tables are internal: the columns are not-accessible, so nothing reads the
# placeholder over SNMP, and config.py overwrites it in the same call.
#
# Eight octets because that is the SIZE minimum each column states. Before the
# generated modules were separated from what was written into them by hand,
# this was an invented DEFVAL sitting in pysmi-0.1.3 output where it read as
# something the ASN.1 had asked for.

_PLACEHOLDER = "\x00" * 8

for _column in (
    pysnmpUsmSecretAuthKey,
    pysnmpUsmSecretPrivKey,
    pysnmpUsmKeyAuthLocalized,
    pysnmpUsmKeyPrivLocalized,
    pysnmpUsmKeyAuth,
    pysnmpUsmKeyPriv,
):
    # The column's own syntax, cloned to carry a value: createTest builds each
    # cell with self.syntax.clone(), which keeps the value when the syntax it
    # clones from has one and produces a schema object when it does not.
    _column.syntax = _column.syntax.clone(_PLACEHOLDER)

del _column
