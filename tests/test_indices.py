"""Ordering guarantees of the index mappings in pysnmp.smi.indices.

Both classes exist to impose an order on their keys that is not insertion
order, so every way of walking one has to agree. `keys()` used to be the only
one that did: `for k in d` fell through to `dict.__iter__` and handed back
insertion order instead, which silently changed the answer at any call site
that dropped the `.keys()`. See pysnmp/pysnmp#178.
"""

from math import ceil, log2

from pysnmp.smi.indices import OidOrderedDict, OrderedDict


def _comparisonsPerLookup(rows):
    """How many key comparisons one `nextKey` costs on a mapping of `rows` keys.

    `nextKey` is documented to order keys through `sortingKey` so that the search
    and the sort cannot disagree, and for a tuple key that returns the key
    itself -- so every comparison the search makes lands on one of the keys
    stored here. Counting them says how many keys the search looked at.

    `__lt__` catches a bisect, `__eq__` catches the `in`/`index` scan this
    implementation replaced, and `__gt__` catches a hand-rolled one. Both sides
    of every comparison are these, so the left operand's method always runs.
    """
    counted = [0]

    class CountingOid(tuple):
        """An OID tuple that counts comparisons made against it."""

        __hash__ = tuple.__hash__

        def __lt__(self, other):
            counted[0] += 1
            return tuple.__lt__(self, other)

        def __gt__(self, other):
            counted[0] += 1
            return tuple.__gt__(self, other)

        def __eq__(self, other):
            counted[0] += 1
            return tuple.__eq__(self, other)

    mapping = OidOrderedDict()
    for i in range(rows):
        mapping[CountingOid((1, 3, 6, 1, 2, 1, i))] = i

    # The far end of the mapping, where a scan is worst. A key that is present
    # is the case the old code scanned twice over.
    target = CountingOid((1, 3, 6, 1, 2, 1, rows - 2))

    # The first lookup sorts the keys, which is n log n comparisons that say
    # nothing about the search. Pay it, then start counting.
    mapping.nextKey(target)
    counted[0] = 0
    mapping.nextKey(target)

    return counted[0]


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
        """One lookup examines about log2(n) keys, not n of them.

        Counted rather than timed. This assertion used to compare wall-clock
        time between two mapping sizes and allow a 3x ratio, but the ratio a
        correct implementation actually produces is ~2 -- ten times the rows
        cost more than one extra bisection step, because the working set grows
        too -- so the real headroom was ~1.5x on measurements of a few
        milliseconds. That is thin enough that an ordinary scheduling hiccup on
        a shared runner failed it.

        Comparisons are the thing the bisect changed, and they do not depend on
        how busy the machine is: a bisect makes about log2(n) of them, the scan
        this replaced made about 2n. Measured here, the separation is 12 versus
        3998 at 2 000 rows and 15 versus 39 998 at 20 000 -- hundreds of times,
        against the 1.5x the clock offered.
        """
        small = _comparisonsPerLookup(2000)
        large = _comparisonsPerLookup(20000)

        # log2(2 000) is 11 and log2(20 000) is 15; the measured counts are 12
        # and 15. The slack is for a re-implementation that probes slightly
        # differently, not for anything proportional to the row count.
        assert small <= ceil(log2(2000)) + 4
        assert large <= ceil(log2(20000)) + 4

        # And the point the name makes: ten times the keys is a handful more
        # comparisons, not ten times as many. Measured difference is 3.
        assert large - small <= 8
