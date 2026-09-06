"""Ordering guarantees of the index mappings in pysnmp.smi.indices.

Both classes exist to impose an order on their keys that is not insertion
order, so every way of walking one has to agree. `keys()` used to be the only
one that did: `for k in d` fell through to `dict.__iter__` and handed back
insertion order instead, which silently changed the answer at any call site
that dropped the `.keys()`. See pysnmp/pysnmp#178.
"""

from pysnmp.smi.indices import OidOrderedDict, OrderedDict


class TestOrderedDict:
    """Keys sort, whichever way you ask for them."""

    def _built(self):
        d = OrderedDict()
        for key in ("charlie", "alpha", "bravo"):
            d[key] = key.upper()
        return d

    def test_keys_are_sorted(self):
        assert self._built().keys() == ["alpha", "bravo", "charlie"]

    def test_iteration_matches_keys(self):
        d = self._built()
        assert list(d) == d.keys()

    def test_builtins_that_iterate_match_keys(self):
        d = self._built()
        assert list(dict(d)) == d.keys()
        assert [k for k in d] == d.keys()  # noqa: C416

    def test_items_and_values_follow_the_same_order(self):
        d = self._built()
        assert [k for k, _ in d.items()] == d.keys()
        assert d.values() == [k.upper() for k in d]

    def test_deletion_keeps_the_order(self):
        d = self._built()
        del d["bravo"]
        assert list(d) == ["alpha", "charlie"]


class TestOidOrderedDict:
    """Keys sort as OIDs -- numerically per arc, not as strings."""

    def _built(self):
        d = OidOrderedDict()
        # As strings these sort 1.3.6.1.10, 1.3.6.1.2, 1.3.6.1.9 -- the point
        # of the class is that they must not.
        for key in ("1.3.6.1.9", "1.3.6.1.10", "1.3.6.1.2"):
            d[key] = key
        return d

    def test_keys_are_in_oid_order(self):
        assert self._built().keys() == ["1.3.6.1.2", "1.3.6.1.9", "1.3.6.1.10"]

    def test_iteration_matches_keys(self):
        d = self._built()
        assert list(d) == d.keys()

    def test_tuple_keys_iterate_in_order(self):
        d = OidOrderedDict()
        for key in ((1, 3, 6, 1, 9), (1, 3, 6, 1, 10), (1, 3, 6, 1, 2)):
            d[key] = key
        assert list(d) == [(1, 3, 6, 1, 2), (1, 3, 6, 1, 9), (1, 3, 6, 1, 10)]
