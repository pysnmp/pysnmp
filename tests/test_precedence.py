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
    have ranked anything. Six of the seven vectors resolved differently, which
    became pysnmp/pysnmp#234; the composite now applies the rule as far as a
    corpus carries it, and :py:class:`TestCrossCorpusDivergence` holds the two
    vectors that remain -- both turning on a term no corpus column records.

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
from pysnmp.smi.corpus import CompositeMibCorpus, MibCorpus, best_by_revision


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
    build, so ``CompositeMibCorpus`` has to rank the answers itself.

    Since pysnmp/pysnmp#234 it ranks them by the corpus rule rather than by
    revision alone: ``(obsolete, tier, revision, name)``. Two of pysmi's seven
    terms cannot be recovered from a corpus at all, and the vectors that turn
    on those two are recorded below. Everything else now agrees.
    """

    #: The ``oid_precedence`` vectors a composite still answers differently,
    #: and why the term cannot be read. A vector added later for a term the
    #: composite also cannot carry fails
    #: :py:meth:`test_divergence_is_exactly_what_is_recorded` rather than
    #: passing unnoticed, and a term that starts being read fails it too.
    DIVERGES = {
        "oid-module-identity-anchor-beats-object-identity": (
            "anchor class: how strongly a module claims the arc is settled at "
            "build time and is not carried into oid_index, so no reader can "
            "recover it -- pysnmp/pysmi would have to add a column"
        ),
        "oid-higher-rfc-breaks-an-equal-revision": (
            "publishing RFC: not a corpus column at all, so no reader can "
            "apply this one"
        ),
    }

    def _acrossCorpora(self, directory, vector):
        """What a composite answers, with each module in a corpus of its own.

        One corpus per module is the shape the rule exists for -- a
        distribution corpus and a vendor one anchoring the same arc -- and it
        is the only way to ask a composite anything, since two modules in one
        corpus are ranked by pysmi at build time instead.
        """
        corpora = [
            _build_corpus(str(directory / f"{m['module']}.db"), {"modules": [m]})
            for m in vector["modules"]
        ]

        composite = CompositeMibCorpus(*corpora)

        try:
            return composite.anchor(pysmi_precedence.CONTESTED)

        finally:
            composite.close()

    @pytest.mark.parametrize("vector", _vectors("oid_precedence"), ids=_identify)
    def test_divergence_is_exactly_what_is_recorded(self, tmp_path, vector):
        found = self._acrossCorpora(tmp_path, vector)
        agrees = found == vector["expect"]

        assert agrees is (vector["id"] not in self.DIVERGES), (
            f"{vector['id']}: across corpora this resolves to {found} and "
            f"within one corpus to {vector['expect']}. DIVERGES records this "
            f"vector as "
            f"{'diverging' if vector['id'] in self.DIVERGES else 'agreeing'}, "
            f"so either a term started being read or one stopped. "
            f"{vector['why']}"
        )

    @pytest.mark.parametrize(
        "vector_id",
        [
            "oid-obsolete-loses-to-live-however-new-it-is",
            "oid-lower-tier-wins-over-a-newer-revision",
        ],
    )
    def test_the_two_terms_that_matter_are_applied(self, tmp_path, vector_id):
        """Tier and obsolete, named individually rather than left to the sweep.

        These are the two #234 was filed for. A vendor tree bundling its own
        copy of a standard MIB is the ordinary case, not a corner, and before
        #234 the newer copy took the arc. The sweep above would go on passing
        if either of these regressed and the vector were quietly added to
        DIVERGES, so they are asserted where that would be conspicuous.
        """
        vector = next(x for x in _vectors("oid_precedence") if x["id"] == vector_id)

        assert self._acrossCorpora(tmp_path, vector) == vector["expect"], vector["why"]

    def test_the_terms_that_cannot_be_read_are_still_absent(self, tmp_path):
        """Evidence that DIVERGES is a schema limit, not an unfinished job.

        Anchor class and RFC number are the two, and neither is a column a
        reader could consult. Asserting that here keeps the pair honest: if
        pysnmp/pysmi ever carries them, this fails and DIVERGES shrinks.
        """
        vector = next(
            x
            for x in _vectors("oid_precedence")
            if x["id"] == "oid-module-identity-anchor-beats-object-identity"
        )

        corpus = _build_corpus(str(tmp_path / "anchor.db"), vector)

        try:
            record = corpus.module(vector["modules"][0]["module"])

        finally:
            corpus.close()

        assert "anchor" not in record
        assert "rfc" not in record
