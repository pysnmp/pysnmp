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


class TestNextKey:
    """`nextKey` -- the agent's GETNEXT step.

    It used to special-case a key that is present, with `key in keys` followed
    by `keys.index(key)`: two full linear scans of a sorted list. Reaching the
    bisect at all meant paying the `in` scan first, so both branches were O(n)
    and a walk of an n-row table was O(n**2). One `bisect_right` answers both
    cases, because it already returns the index *after* an equal element.

    The equivalence is the whole argument for the change, so it is pinned here
    rather than left to inspection.
    """

    def _built(self):
        d = OidOrderedDict()
        for i in (1, 3, 5, 7):
            d[(1, 3, 6, 1, i)] = i
        return d

    def test_a_present_key_yields_its_successor(self):
        assert self._built().nextKey((1, 3, 6, 1, 3)) == (1, 3, 6, 1, 5)

    def test_an_absent_key_between_two_present_ones_yields_the_later(self):
        assert self._built().nextKey((1, 3, 6, 1, 4)) == (1, 3, 6, 1, 5)

    def test_an_absent_key_before_the_first_yields_the_first(self):
        assert self._built().nextKey((1, 3, 6, 1, 0)) == (1, 3, 6, 1, 1)

    def test_a_longer_key_under_a_present_one_yields_the_next_sibling(self):
        # The everyday GETNEXT shape: the manager asks about an instance OID
        # below a row, which is never itself a key.
        assert self._built().nextKey((1, 3, 6, 1, 3, 0)) == (1, 3, 6, 1, 5)

    def test_the_last_key_raises(self):
        import pytest

        with pytest.raises(KeyError):
            self._built().nextKey((1, 3, 6, 1, 7))

    def test_past_the_last_key_raises(self):
        import pytest

        with pytest.raises(KeyError):
            self._built().nextKey((1, 3, 6, 1, 9))

    def test_successive_calls_walk_the_whole_mapping(self):
        d = self._built()
        walked = []
        key = (1, 3, 6, 1, 0)
        while True:
            try:
                key = d.nextKey(key)
            except KeyError:
                break
            walked.append(key)

        assert walked == d.keys()

    def test_the_search_follows_oid_order_not_string_order(self):
        # The bisect has to order keys the way the sort did. With string keys
        # the two used to disagree: sorting is numeric per arc, while a plain
        # bisect compares the strings, which would put 1.3.6.1.2 after
        # 1.3.6.1.10.
        d = OidOrderedDict()
        for key in ("1.3.6.1.9", "1.3.6.1.10", "1.3.6.1.2"):
            d[key] = key

        assert d.nextKey("1.3.6.1.2") == "1.3.6.1.9"
        assert d.nextKey("1.3.6.1.9") == "1.3.6.1.10"

        # An *absent* key is where the two orderings used to part company: only
        # a present key took the exact-match branch, so everything else was
        # bisected lexically against an OID-sorted list. 1.3.6.1.11 is past the
        # last key numerically, but sorts before 1.3.6.1.2 as a string, so the
        # old code returned the first key instead of running off the end.
        import pytest

        with pytest.raises(KeyError):
            d.nextKey("1.3.6.1.11")

    def test_the_base_class_still_orders_plainly(self):
        d = OrderedDict()
        for key in ("charlie", "alpha", "bravo"):
            d[key] = key

        assert d.nextKey("alpha") == "bravo"
        assert d.nextKey("alphb") == "bravo"

    def test_a_mapping_mutated_after_a_search_re_sorts(self):
        d = self._built()

        assert d.nextKey((1, 3, 6, 1, 3)) == (1, 3, 6, 1, 5)

        d[(1, 3, 6, 1, 4)] = 4

        assert d.nextKey((1, 3, 6, 1, 3)) == (1, 3, 6, 1, 4)

    def test_it_is_not_linear_in_the_number_of_keys(self):
        # A bound rather than a benchmark: two mappings an order of magnitude
        # apart in size, both searched at their far end, where the old linear
        # scan was worst. O(log n) puts the ratio near 1; the old code was
        # ~10x. The threshold is loose enough not to be a flake and tight
        # enough that a reintroduced scan fails it.
        import time

        def elapsed(rows):
            d = OidOrderedDict()
            for i in range(rows):
                d[(1, 3, 6, 1, 2, 1, i)] = i
            target = (1, 3, 6, 1, 2, 1, rows - 2)
            start = time.perf_counter()
            for _ in range(2000):
                d.nextKey(target)
            return time.perf_counter() - start

        small = elapsed(2000)
        large = elapsed(20000)

        assert large < small * 3
