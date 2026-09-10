"""pysmi's precedence vectors, run against this repository's rankers.

"Newest MODULE-IDENTITY revision wins, configured order breaks ties only" is
written twice here and twice in pysmi, in repositories that cannot import each
other: pysmi is an optional dependency as of #218, and pysmi cannot import
pysnmp at all. That leaves four copies of one rule with nothing holding them
together, and a disagreement between them does not surface where it is caused.
It surfaces when the same two definitions of a module resolve differently
depending on whether they arrived as compiled ``.py`` files or as corpora, and
a trap decodes against the wrong one.

``pysmi.corpus.precedence`` publishes the rule as data for exactly this reason,
the way ``pysmi.corpus.conformance`` publishes the reader contract. This is the
consumer half (``pysnmp/pysmi#248``, pysnmp/pysnmp#232). What is asserted here:

``normalise_revision``
    Not implemented in this repository and deliberately so -- a revision
    reaches pysnmp already normalised, from the corpus ``module.revision``
    column or from the ``PYSNMP_MODULE_REVISION`` constant pysmi writes into a
    generated module. What these vectors pin here is instead the *assumption*
    both rankers make about that output: that an accepted stamp is fixed-width,
    so comparing two of them as strings orders them by date, and that a refused
    one arrives as ``None``. Both rankers compare with ``str`` ordering, so a
    normal form that ever varied in width would misorder silently.

``module_precedence``
    Run against both implementations. :py:func:`~pysnmp.smi.corpus.best_by_revision`
    ranks a module carried by several corpora and answers the winner;
    :py:meth:`~pysnmp.smi.builder.MibBuilder._candidates` ranks a module found in
    several MIB directories and answers the whole order, losers included.

``oid_precedence``
    The corpus rule, which carries terms -- obsolete, tier, how the module
    claims the arc, publishing RFC -- that a directory of files has nowhere to
    put. pysnmp does not implement it: ``rank_index`` runs in pysmi at build
    time and the answer is a row in ``oid_index``. So these vectors are run as
    a round trip, rank to write to read, which is the part that can break here:
    a reader that resolved ``oid_index`` wrongly would lose the ranking just as
    completely as one that computed it wrongly.

    Running them also answered a question nobody had asked: how much of that
    rule survives a search across *several* corpora, where there is no build to
    have ranked anything. Six of the seven vectors resolve differently there,
    because the composite reads only the revision term. That is pysnmp/pysnmp#234,
    and :py:class:`TestCrossCorpusDivergence` pins it rather than skipping it.

The vectors ``why`` field is the failure message throughout, so a break says
what decision was violated rather than which tuple did not match.
"""

import pytest

# Imported rather than skipped over, for the reason given at the head of
# tests/test_corpus.py: a ``pytest.importorskip`` here can silently hide the
# whole module, and anything able to collect this file has the dev group
# installed.
from pysmi.corpus import precedence as pysmi_precedence
from pysmi.corpus.db import write_db
from pysmi.corpus.index import rank_index
from pysmi.corpus.namespace import TIERS

from pysnmp.smi.builder import MODULE_REVISION, MibBuilder, revisionOf
from pysnmp.smi.corpus import MibCorpus, best_by_revision


def _vectors(operation):
    """The published vectors for one operation, in publication order."""
    return [vector for vector in pysmi_precedence.VECTORS if vector["op"] == operation]


def _identify(vector):
    """A vector's id, for the test name pytest reports."""
    return vector["id"]


def _build_corpus(path, vector):
    """A corpus holding exactly the modules one ``oid_precedence`` vector names.

    The ranking is pysmi's, computed here the way a real build computes it, so
    what the reader is asked afterwards is whether it returns the winner the
    rule chose -- not whether it can rank, which is not its job.
    """
    documents = [
        (module["module"], module["document"], module["tier"], module["rfc"])
        for module in vector["modules"]
    ]

    # pysmi's TIERS orders (standard, draft, vendor); the vectors carry the
    # index rather than the name, and the module table wants the name.
    tiers = {module["module"]: TIERS[module["tier"]] for module in vector["modules"]}

    write_db(
        path,
        documents,
        tiers,
        ranked=rank_index(documents),
        corpusId="pysnmp-precedence",
    )

    return MibCorpus(path)


class _StubMibSource:
    """A MIB source carrying exactly one module at one revision.

    ``_candidates`` reads a revision off the code object a source hands back,
    never off its text, so a stub has to hand back a real code object. Compiling
    the one assignment ``revisionOf`` looks for is enough and keeps the fixture
    honest: it is disassembled by the same code path that reads a shipped
    module.
    """

    def __init__(self, name, module, revision):
        self._name = name
        self._module = module
        self._revision = revision

    def __repr__(self):
        """Where this source claims to be, for debug logging."""
        return f"_StubMibSource({self._name!r})"

    def init(self):
        """Already open."""
        return self

    def fullPath(self, *args):
        """Where a module would live in this source."""
        return self._name + ("/" + args[0] if args else "")

    def read(self, modName):
        """The module as a code object, or ``OSError`` when this is not it."""
        if modName != self._module:
            raise OSError(2, "No such file or directory", modName)

        source = (
            f"{MODULE_REVISION} = {self._revision!r}\n"
            if self._revision is not None
            else "# a module stating no revision\n"
        )

        return compile(source, self.fullPath(modName), "exec"), ".py"


class TestRevisionShape:
    """What both rankers assume about a normalised revision.

    Neither of them normalises, and neither should: the normalisation is
    pysmi's, and its output is what reaches here. But both compare revisions as
    strings, which is only chronological ordering while every accepted stamp is
    the same width. These vectors are where that assumption is anchored to the
    producer rather than restated in a comment.
    """

    @pytest.mark.parametrize("vector", _vectors("normalise_revision"), ids=_identify)
    def test_accepted_stamps_are_fixed_width(self, vector):
        expect = vector["expect"]

        if expect is None:
            pytest.skip("refused stamps are covered by the vector below")

        assert len(expect) == 13, vector["why"]
        assert expect.endswith("Z"), vector["why"]
        assert expect[:12].isdigit(), vector["why"]

    @pytest.mark.parametrize("vector", _vectors("normalise_revision"), ids=_identify)
    def test_refused_stamps_arrive_as_none(self, vector):
        if vector["expect"] is not None:
            pytest.skip("accepted stamps are covered by the vector above")

        # A refused stamp is the undated case, and both rankers answer that by
        # standing down to configured order rather than by guessing. HPR-MIB's
        # thirteen-digit LAST-UPDATED is the one that matters: ranked rather
        # than refused it sorts above every real date forever.
        assert best_by_revision([("first", None), ("second", "202406010000Z")]) == (
            "first"
        ), vector["why"]

    def test_string_order_is_date_order(self):
        """The property the whole rule rides on, stated once.

        Every accepted stamp being ``YYYYMMDDHHMMZ`` is what makes ``max()``
        over raw strings a chronological answer. Widening the year is part of
        it -- a two-digit form compared against a four-digit one orders by its
        first character.
        """
        stamps = [
            vector["expect"]
            for vector in _vectors("normalise_revision")
            if vector["expect"] is not None
        ]

        assert sorted(stamps) == sorted(stamps, key=lambda stamp: stamp[:12])


class TestModulePrecedence:
    """The module-name rule, against both of this repository's copies of it.

    Three of the four implementations of the rule are this one, so a vector
    failing in one of these two and passing in the other is the interesting
    outcome: it means the builder and the corpus reader would answer the same
    question differently, which is the defect neither one's own tests can see.
    """

    @pytest.mark.parametrize("vector", _vectors("module_precedence"), ids=_identify)
    def test_corpus_ranker_picks_the_winner(self, vector):
        """``best_by_revision``: the same module carried by several corpora."""
        candidates = [
            (index, candidate["revision"])
            for index, candidate in enumerate(vector["candidates"])
        ]

        assert best_by_revision(candidates) == vector["expect"]["winner"], vector["why"]

    @pytest.mark.parametrize("vector", _vectors("module_precedence"), ids=_identify)
    def test_builder_ranker_orders_every_candidate(self, vector):
        """``_candidates``: the same module found in several MIB directories.

        The whole order is asserted, not just the winner. The losers are the
        shadowed copies a deployment needs reported, so their order is part of
        the answer.
        """
        module = vector["candidates"][0]["module"]
        sources = [
            _StubMibSource(f"source-{index}", module, candidate["revision"])
            for index, candidate in enumerate(vector["candidates"])
        ]

        builder = MibBuilder()
        builder.setMibSources(*sources)

        ranked = builder._candidates(module)
        order = [sources.index(source) for source, _, _ in ranked]

        assert order == vector["expect"]["order"], vector["why"]

    @pytest.mark.parametrize("vector", _vectors("module_precedence"), ids=_identify)
    def test_both_rankers_agree(self, vector):
        """The point of running one rule against two implementations.

        Stated separately from the two vector assertions above because it is a
        different claim: not that each side is right, but that they cannot
        drift apart from each other even if the published vectors were to move.
        """
        module = vector["candidates"][0]["module"]
        revisions = [candidate["revision"] for candidate in vector["candidates"]]

        sources = [
            _StubMibSource(f"source-{index}", module, revision)
            for index, revision in enumerate(revisions)
        ]

        builder = MibBuilder()
        builder.setMibSources(*sources)

        byDirectory = sources.index(builder._candidates(module)[0][0])
        byCorpus = best_by_revision(list(enumerate(revisions)))

        assert byDirectory == byCorpus, vector["why"]

    def test_revision_is_read_off_the_code_object(self):
        """The stub is only honest if ``revisionOf`` reads it the shipped way.

        Every assertion in this class rests on a compiled stub standing in for
        a generated module. If ``revisionOf`` stopped finding the constant --
        a rename, an emitted form ``dis`` reports differently -- the stubs
        would all read as undated and every vector above would pass by falling
        through to configured order, which is the wrong answer arrived at
        quietly.
        """
        dated = _StubMibSource("s", "EXAMPLE-MIB", "202406010000Z")
        undated = _StubMibSource("s", "EXAMPLE-MIB", None)

        assert revisionOf(dated.read("EXAMPLE-MIB")[0]) == "202406010000Z"
        assert revisionOf(undated.read("EXAMPLE-MIB")[0]) is None


class TestOidPrecedence:
    """The corpus rule, asserted as a round trip through a real corpus.

    pysnmp has no implementation of this rule to compare against and is not
    meant to: the terms it turns on -- obsolete, tier, anchor class, publishing
    RFC -- are read off the whole corpus at build time, and what reaches a
    reader is one ``oid_index`` row per OID. So the vectors are run by ranking
    with pysmi, writing a corpus, and asking this repository's reader who owns
    the contested arc. A reader that resolved the index wrongly loses the
    ranking exactly as thoroughly as one that computed it wrongly, and that
    failure is this repository's to catch.
    """

    @pytest.fixture
    def contested(self, tmp_path):
        """Build a one-arc corpus from a vector and return its reader."""

        def build(vector):
            return _build_corpus(str(tmp_path / f"{vector['id']}.db"), vector)

        return build

    @pytest.mark.parametrize("vector", _vectors("oid_precedence"), ids=_identify)
    def test_reader_returns_the_ranked_owner(self, contested, vector):
        corpus = contested(vector)

        try:
            assert corpus.anchor(pysmi_precedence.CONTESTED) == vector["expect"], (
                vector["why"]
            )

        finally:
            corpus.close()

    @pytest.mark.parametrize("vector", _vectors("oid_precedence"), ids=_identify)
    def test_chopping_reaches_the_same_owner(self, contested, vector):
        """The trap path: an instance OID below the contested arc.

        ``find_module`` is what a decode actually calls, and it shortens the
        OID until something resolves. An arc below the contested one appears
        in no module at all, so it must chop down to the contested arc and
        answer with the module that won it -- the same module ``anchor``
        returns for the arc itself.
        """
        corpus = contested(vector)

        try:
            assert (
                corpus.find_module(f"{pysmi_precedence.CONTESTED}.1.0")
                == vector["expect"]
            ), vector["why"]

        finally:
            corpus.close()


class TestCrossCorpusDivergence:
    """How much of the corpus rule survives a search across several corpora.

    Within one corpus the answer is pysmi's, computed over every module the
    build saw and stored in ``oid_index``. Across corpora there is no such
    build: ``CompositeMibCorpus`` asks each corpus who anchors the arc and
    ranks the answers with ``best_by_revision``, the module-name rule, because
    revision is the only term it reads. Of the seven terms the corpus rule
    turns on, six are therefore not applied between corpora, and the answers
    differ -- a vendor corpus republished last week takes an arc from the
    standard definition of it, which is the outcome within a corpus is
    specifically ordered to prevent.

    This is a gap, not a decision, and it is pysnmp/pysnmp#234. It is pinned
    here rather than skipped so that the day it is closed, these assertions
    fail and say so: an unasserted gap and a regression look identical.
    """

    #: Every ``oid_precedence`` vector the composite answers differently, and
    #: the term it turns on that the composite does not read. A vector added
    #: later for a term the composite also cannot carry fails
    #: :py:meth:`test_divergence_is_exactly_what_is_recorded` rather than
    #: passing unnoticed, and a term that starts being read fails it too.
    DIVERGES = {
        "oid-obsolete-loses-to-live-however-new-it-is": (
            "status: a module whose every object is obsolete describes an arc "
            "nobody should decode against, and the composite reads no status"
        ),
        "oid-lower-tier-wins-over-a-newer-revision": (
            "tier: the corpus module table carries one, and the composite "
            "does not compare it -- so a vendor corpus outranks the standard "
            "definition by being newer, which is the case that matters most"
        ),
        "oid-module-identity-anchor-beats-object-identity": (
            "anchor class: how strongly a module claims the arc is settled at "
            "build time and is not carried into oid_index"
        ),
        "oid-higher-rfc-breaks-an-equal-revision": (
            "publishing RFC: not a corpus column at all, so no reader can "
            "apply this one"
        ),
        "oid-module-name-makes-the-rule-total": (
            "module name as final term: equal revisions fall to configured "
            "order instead, so the answer is stable but is the caller's order "
            "rather than the rule's"
        ),
        "oid-anchorless-module-loses-to-an-anchored-one": (
            "undated candidate: within a corpus it loses, across corpora it "
            "disables the comparison entirely, because a composite has the "
            "configured order to fall back on and a corpus has nothing"
        ),
    }

    def _byRevisionOnly(self, vector):
        """What the composite answers for a vector, ranking on revision alone."""
        return best_by_revision(
            [
                (
                    module["module"],
                    module["document"].get("identity", {}).get("lastupdated"),
                )
                for module in vector["modules"]
            ]
        )

    @pytest.mark.parametrize("vector", _vectors("oid_precedence"), ids=_identify)
    def test_divergence_is_exactly_what_is_recorded(self, vector):
        agrees = self._byRevisionOnly(vector) == vector["expect"]

        assert agrees is (vector["id"] not in self.DIVERGES), (
            f"{vector['id']}: across corpora this resolves to "
            f"{self._byRevisionOnly(vector)} and within one corpus to "
            f"{vector['expect']}. DIVERGES records this vector as "
            f"{'diverging' if vector['id'] in self.DIVERGES else 'agreeing'}, "
            f"so either #234 moved or a term was added. {vector['why']}"
        )

    def test_the_one_term_that_does_carry_is_revision(self):
        """The half that works, stated on its own.

        Whatever else is missing, two corpora carrying the same module at two
        revisions resolve to the newer one, which is the case an operator
        actually creates by adding a corpus to an existing deployment.
        """
        vector = next(
            vector
            for vector in _vectors("oid_precedence")
            if vector["id"] == "oid-newest-revision-wins"
        )

        assert self._byRevisionOnly(vector) == vector["expect"], vector["why"]

    def test_tier_is_readable_even_though_it_is_not_read(self, tmp_path):
        """#234 is implementable, and this is the evidence for that claim.

        The gap above would be permanent if the terms it turns on were absent
        from a corpus. Tier is not: it is a column on the ``module`` table and
        this reader already returns it, so a composite that wanted to compare
        tiers before revisions has the value in hand. Recording that here keeps
        the issue from being closed as won't-fix on a false premise.
        """
        vector = next(
            vector
            for vector in _vectors("oid_precedence")
            if vector["id"] == "oid-lower-tier-wins-over-a-newer-revision"
        )

        corpus = _build_corpus(str(tmp_path / "tiers.db"), vector)

        try:
            tiers = {
                module["module"]: corpus.module(module["module"])["tier"]
                for module in vector["modules"]
            }

        finally:
            corpus.close()

        assert tiers == {"VENDOR-MIB": "vendor", "STANDARD-MIB": "standard"}
