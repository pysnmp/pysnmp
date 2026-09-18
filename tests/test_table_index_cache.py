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
