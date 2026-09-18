"""The two caches bolted onto ``MibTableRow`` index conversion.

``getInstIdFromIndices`` and ``getIndicesFromInstId`` each memoize their own
direction, and each is wrong in its own way. Everything here goes through the
public methods rather than reaching into the cache, so what is pinned is the
behaviour a caller sees.
"""

import pytest
from pyasn1.type import univ

from pysnmp.smi.builder import MibBuilder


@pytest.fixture(scope="module")
def ifEntry():
    """``IF-MIB::ifEntry`` -- one Integer32 index, the simplest real row."""
    built = MibBuilder()
    built.loadModules("IF-MIB")
    (row,) = built.importSymbols("IF-MIB", "ifEntry")

    return row


class TestIndicesToInstId:
    """``getInstIdFromIndices()`` -- indices in, instance OID out."""

    def test_a_schema_object_among_the_indices_does_not_fail_the_call(self, ifEntry):
        # etingof/pysnmp#444. Looking the index tuple up in the cache hashes it,
        # and hashing a pyasn1 *schema* object -- a type with no value attached
        # -- raises PyAsn1Error, not TypeError. Guarding on TypeError alone let
        # it escape index resolution with the reporter's
        # 'Attempted "__hash__" operation on ASN.1 schema object'.
        #
        # ifEntry declares one index, so the second argument is never consumed
        # and the row is perfectly able to answer; only the cache lookup on the
        # way in ever touched it.
        assert ifEntry.getInstIdFromIndices(3, univ.Integer()) == (3,)

    def test_an_unhashable_index_does_not_fail_the_call(self, ifEntry):
        # The case the guard was written for in the first place, kept honest.
        assert ifEntry.getInstIdFromIndices(3, [1, 2]) == (3,)

    def test_the_uncacheable_path_leaves_cacheable_bound(self, ifEntry):
        # Widening the guard without setting `cacheable` on that path would
        # trade the PyAsn1Error for an UnboundLocalError at the foot of the
        # method, where `if cacheable:` reads it.
        assert ifEntry.getInstIdFromIndices(4, univ.Integer()) == (4,)
        assert ifEntry.getInstIdFromIndices(4, univ.Integer()) == (4,)

    def test_a_valueless_index_the_row_does_consume_still_reports(self, ifEntry):
        # The cache is not the only thing that cannot work with a schema object:
        # there is no value to encode, so the clone below it fails too. That is
        # inherent rather than a defect, and the error should say so plainly
        # rather than being mistaken for the cache bug above.
        with pytest.raises(Exception, match="schema object"):
            ifEntry.getInstIdFromIndices(univ.Integer())

    def test_a_hashable_index_still_caches(self, ifEntry):
        assert ifEntry.getInstIdFromIndices(11) == (11,)
        assert ifEntry.getInstIdFromIndices(11) == (11,)


class TestInstIdToIndices:
    """``getIndicesFromInstId()`` -- instance OID in, indices out."""

    def test_distinct_instance_oids_resolve_to_distinct_indices(self, ifEntry):
        assert [int(x) for x in ifEntry.getIndicesFromInstId((7,))] == [7]
        assert [int(x) for x in ifEntry.getIndicesFromInstId((9,))] == [9]

    def test_the_empty_instance_oid_is_not_polluted_by_earlier_lookups(self, ifEntry):
        # The cache used to be written under the *remainder* left after parsing,
        # which is () on every success. So every call overwrote one shared entry,
        # and getIndicesFromInstId(()) handed back whichever row was parsed last
        # -- [9] here rather than the empty tuple a row with no indices left has.
        ifEntry.getIndicesFromInstId((7,))
        ifEntry.getIndicesFromInstId((9,))

        # An empty instance OID is too short for a row that declares an index,
        # so the honest answer is the short-OID stand-in -- never row 9's.
        assert ifEntry.getIndicesFromInstId(()) == ((),)

    def test_a_repeated_lookup_returns_the_same_indices(self, ifEntry):
        # Reads keyed on the full instance OID and writes keyed on the remainder
        # meant the cache never once answered a real lookup. It should now, and
        # what it answers with has to be right.
        first = ifEntry.getIndicesFromInstId((13,))
        second = ifEntry.getIndicesFromInstId((13,))

        assert [int(x) for x in first] == [13]
        assert [int(x) for x in second] == [13]

    def test_a_cached_lookup_survives_an_unrelated_one(self, ifEntry):
        # The pollution in the other direction: a second row's parse used to
        # overwrite the single () entry, so whichever entry did exist was never
        # the one being asked for.
        assert [int(x) for x in ifEntry.getIndicesFromInstId((21,))] == [21]
        assert [int(x) for x in ifEntry.getIndicesFromInstId((22,))] == [22]
        assert [int(x) for x in ifEntry.getIndicesFromInstId((21,))] == [21]

    def test_an_unparseable_index_is_not_cached_as_if_it_were_valid(self):
        # A row whose index does not match the compiled MIB returns the
        # unconsumed remainder standing in for its indices. Whatever is decided
        # about that (see #252), it must not reach the cache, where it would be
        # served to a later caller asking about a different OID entirely.
        built = MibBuilder()
        built.loadModules("SNMP-VIEW-BASED-ACM-MIB")
        (row,) = built.importSymbols("SNMP-VIEW-BASED-ACM-MIB", "vacmAccessEntry")

        # Far too few sub-identifiers for this row's four indices.
        assert row.getIndicesFromInstId((1,)) == ((1,),)

        # If that remainder had been cached it would have been cached under (),
        # and this lookup would hand back ((1,),) instead of its own stand-in.
        assert row.getIndicesFromInstId(()) == ((),)
