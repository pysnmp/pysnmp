"""Reading a MIB corpus, and building MIB objects out of it.

Two things are being pinned here and they pull in opposite directions.

**Nothing changes for anyone who does not ask for it.** A ``MibBuilder`` with
no corpus configured resolves exactly as it did: same sources, same search
order, same objects, same errors. splunk-connect-for-snmp and every other
existing deployment upgrade into this without touching anything, so a test that
a corpus-free builder is untouched is as load-bearing as any test of the corpus
itself.

**What the corpus resolves is the same thing the generated module would have.**
A synthesized ``ifDescr`` is a ``MibTableColumn`` with a ``DisplayString``
syntax and ``readonly`` access, because that is what loading ``IF-MIB.py``
produces. Anything less is a second, subtly different runtime.

The fixture is pysmi's conformance corpus (``pysnmp/pysmi#184``), built here
rather than committed, so the reader is checked against the writer that
produces real corpora rather than against a hand-written database that agrees
with the reader by construction.
"""

import os
import shutil
import sqlite3

import pytest

# Imported rather than skipped over. This was a ``pytest.importorskip``, and
# because the dev group's pysmi floor still named a release predating
# ``pysmi.corpus``, the skip fired for the whole module -- every test in this
# file, not just the vectors -- and CI reported success without running any of
# it. A skip that can hide the entire suite it guards is worse than a
# collection error, and there is nothing for it to protect: pytest itself comes
# from the same dev group as pysmi, so anything able to collect this file has
# the group installed and therefore has a pysmi that publishes the fixture.
from pysmi.corpus import conformance as pysmi_conformance

from pysnmp.smi import error
from pysnmp.smi.builder import MibBuilder
from pysnmp.smi.corpus import (
    APPLICATION_ID,
    SCHEMA_VERSION,
    CompositeMibCorpus,
    MibCorpus,
    oid_from_key,
    oid_key,
    open_corpora,
    subtree_bound,
)


@pytest.fixture(scope="module")
def corpus_path(tmp_path_factory):
    """pysmi's conformance corpus, built fresh."""
    directory = tmp_path_factory.mktemp("corpus")

    return pysmi_conformance.build_fixture(str(directory / "conformance.db"))


@pytest.fixture
def corpus(corpus_path):
    """An open corpus, closed afterwards."""
    opened = MibCorpus(corpus_path)

    yield opened

    opened.close()


#: Where the derived corpus anchors a module of its own, under a subtree the
#: conformance corpus anchors seven arcs higher. This is the shape the
#: longest-prefix rule exists for: a site's own subtree inside a vendor arc the
#: distribution corpus already claims.
PRIVATE_OID = "1.3.6.1.4.1.99999.2.7"

#: An OID the derived corpus anchors to a *different* module at the *same*
#: length the conformance corpus anchors ``SMIV1-MIB``. Nothing but precedence
#: can separate these two, which is what makes it the tie-break case.
CONTESTED_OID = "1.3.6.1.4.1.99996"


@pytest.fixture(scope="module")
def private_path(corpus_path, tmp_path_factory):
    """A second corpus, derived from the first so the two genuinely overlap.

    Copied rather than built independently, because what has to be tested is
    what happens when two corpora carry the *same* module: which one answers,
    and that the other's rows for it stay invisible. Three edits give every
    such case a name to assert on.
    """
    path = str(tmp_path_factory.mktemp("private") / "private.db")
    shutil.copy(corpus_path, path)

    db = sqlite3.connect(path)

    with db:
        # The same module, one node under a different descriptor. Whichever
        # name resolves says which corpus owns FIXTURE-MIB.
        db.execute(
            "UPDATE node SET name = 'privateScalar' "
            "WHERE module = 'FIXTURE-MIB' AND name = 'fixtureScalar'"
        )

        # An IMPORTS row the conformance corpus does not have, so a composite
        # that merged the two would be caught doing it.
        db.execute(
            "INSERT INTO import (module, name, source) "
            "VALUES ('FIXTURE-MIB', 'PrivateOnly', 'PRIVATE-MIB')"
        )

        db.execute(
            "INSERT INTO module (name, tier, oid, lastupdated, revision, "
            "content_hash, nodes) VALUES ('PRIVATE-MIB', 'vendor', ?, "
            "'2026-01-01 00:00', '202601010000Z', 'private', 1)",
            (PRIVATE_OID,),
        )
        db.execute(
            "INSERT INTO node (oid_key, module, name, oid, class) "
            "VALUES (?, 'PRIVATE-MIB', 'privateMib', ?, 'moduleidentity')",
            (oid_key(PRIVATE_OID), PRIVATE_OID),
        )
        db.execute(
            "INSERT INTO oid_index (oid_key, oid, module) VALUES (?, ?, 'PRIVATE-MIB')",
            (oid_key(PRIVATE_OID), PRIVATE_OID),
        )

        # Same anchor, same length, different module.
        db.execute(
            "UPDATE oid_index SET module = 'PRIVATE-MIB' WHERE oid_key = ?",
            (oid_key(CONTESTED_OID),),
        )

        db.execute("UPDATE meta SET value = 'private' WHERE key = 'corpus_id'")

    db.close()

    return path


def _at_revision(source, destination, module, revision):
    """A copy of a corpus stating a different revision for one module.

    The derived corpus is a copy, so every module in it states the revision
    the original does and configured order decides everything. Testing that
    the revision is what decides needs the two to disagree.
    """
    shutil.copy(source, destination)

    db = sqlite3.connect(destination)

    with db:
        db.execute("UPDATE module SET revision = ? WHERE name = ?", (revision, module))

    db.close()

    return destination


@pytest.fixture(scope="module")
def newer_path(private_path, tmp_path_factory):
    """The derived corpus, stating a newer FIXTURE-MIB than the first one."""
    return _at_revision(
        private_path,
        str(tmp_path_factory.mktemp("newer") / "newer.db"),
        "FIXTURE-MIB",
        "202606010000Z",
    )


@pytest.fixture(scope="module")
def older_path(private_path, tmp_path_factory):
    """The derived corpus, stating an older FIXTURE-MIB than the first one."""
    return _at_revision(
        private_path,
        str(tmp_path_factory.mktemp("older") / "older.db"),
        "FIXTURE-MIB",
        "202001010000Z",
    )


@pytest.fixture(scope="module")
def dated_contest_paths(corpus_path, private_path, tmp_path_factory):
    """Both corpora, with both sides of the contested anchor dated.

    ``SMIV1-MIB`` states no revision, which is the whole point of it, so the
    contested anchor falls to configured order. Dating it in *both* corpora --
    it is carried by both, and an undated copy in either would send the
    decision back to order -- turns the same contest into one the revision
    rule can decide.
    """
    directory = tmp_path_factory.mktemp("dated")

    return (
        _at_revision(
            corpus_path, str(directory / "base.db"), "SMIV1-MIB", "201001010000Z"
        ),
        _at_revision(
            private_path, str(directory / "private.db"), "SMIV1-MIB", "201001010000Z"
        ),
    )


def _with_texts(source, destination):
    """A copy of a corpus that claims to carry prose.

    The conformance corpus does not, and ``loadTexts`` on a composite is an
    ``all()`` -- so testing that it is one needs a corpus on the other side of
    the question.
    """
    shutil.copy(source, destination)

    db = sqlite3.connect(destination)

    with db:
        db.execute("UPDATE meta SET value = '1' WHERE key = 'texts'")

    db.close()

    return destination


@pytest.fixture
def composite(corpus_path, private_path):
    """The conformance corpus first, the derived one second."""
    opened = open_corpora([corpus_path, private_path])

    yield opened

    opened.close()


@pytest.fixture
def reversed_composite(corpus_path, private_path):
    """The same two corpora, the other way round."""
    opened = open_corpora([private_path, corpus_path])

    yield opened

    opened.close()


class TestOidKey:
    """What this codec owes beyond the format's own rules.

    The encoding itself -- round-tripping, bytewise order being numeric order,
    a prefix staying a prefix, a parent sorting before its children, the
    subtree bounds, and refusing what is not an OID -- is specified by pysmi
    and asserted by its conformance vectors, which :py:class:`TestConformance`
    runs against *this* implementation. Restating those properties here was
    transcribing a specification into the repository that consumes it, where
    the copy agrees with the original exactly until the original changes.

    What is left is what the vectors cannot say, because it is pysnmp's rather
    than the format's.
    """

    def test_accepts_arcs_as_well_as_text(self):
        # pysmi's codec takes a dotted string. This one also takes the arcs,
        # because callers here hold OIDs as tuples far more often than as
        # text, so it is an affordance of this implementation rather than a
        # property of the encoding.
        assert oid_key((1, 3, 6)) == oid_key("1.3.6")

    @pytest.mark.parametrize("bad", ["", "1.3.six", "not an oid", "1.4294967296"])
    def test_refuses_as_an_smi_error(self, bad):
        # The vectors say a codec must refuse these. They cannot say what it
        # must raise, and the type is this library's contract: a caller
        # catching SmiError to fall back to its MIB sources does not catch
        # ValueError.
        with pytest.raises(error.SmiError):
            oid_key(bad)

    def test_agrees_with_pysmi(self):
        # The two implementations are separate on purpose -- importing pysmi
        # to read a file whose point is that it needs no pysmi would defeat
        # the layering. The vectors pin each side to the specification; this
        # pins them to each other, which is the cheaper check when a vector
        # has not yet been written for some shape.
        from pysmi.corpus.db import oid_key as writer_key

        for oid in ("1.3.6.1.2.1.2.2.1.2", "1.3.256.9.10", "2.0", "1"):
            assert oid_key(oid) == writer_key(oid)


class TestCorpusOpen:
    """What a corpus refuses to be opened as."""

    def test_missing_file(self, tmp_path):
        with pytest.raises(error.SmiError, match="no MIB corpus"):
            MibCorpus(str(tmp_path / "absent.db"))

    def test_a_path_sqlite_cannot_open(self, tmp_path):
        # os.path.exists passes for a directory, and sqlite3.connect raises
        # OperationalError rather than returning something the checks below it
        # can reject. Everything else this class covers is an SmiError, and a
        # caller catching one to fall back to its MIB sources would not catch
        # a bare sqlite3 error.
        directory = tmp_path / "corpus.db"
        directory.mkdir()

        with pytest.raises(error.SmiError, match="cannot open MIB corpus"):
            MibCorpus(str(directory))

    def test_not_a_corpus(self, tmp_path):
        import sqlite3

        path = tmp_path / "other.db"
        connection = sqlite3.connect(str(path))
        connection.execute("CREATE TABLE t (x)")
        connection.commit()
        connection.close()

        with pytest.raises(error.SmiError, match="not a MIB corpus"):
            MibCorpus(str(path))

    def test_unreadable_schema_version(self, corpus_path, tmp_path):
        import shutil
        import sqlite3

        path = tmp_path / "future.db"
        shutil.copy(corpus_path, path)
        connection = sqlite3.connect(str(path))
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
        connection.close()

        # Refused rather than read as far as we understand it: a partial read
        # resolves some OIDs and silently not others.
        with pytest.raises(error.SmiError, match="schema version"):
            MibCorpus(str(path))

    def test_opens_without_a_writable_directory(self, corpus_path, tmp_path):
        # A corpus is mounted read-only from an image volume, so nothing near
        # it is writable and SQLite must not want to be.
        import shutil

        directory = tmp_path / "ro"
        directory.mkdir()
        path = directory / "core.db"
        shutil.copy(corpus_path, path)
        os.chmod(directory, 0o500)

        try:
            opened = MibCorpus(str(path))
            assert opened.modules()
            opened.close()

        finally:
            os.chmod(directory, 0o700)

    # "?" is the character that motivated the escaping and the only one here
    # Windows will not accept in a filename -- mkdir fails with WinError 123
    # before any of this is reached. It is parametrized wherever a directory
    # can be named that, which is every platform but Windows; the other three
    # run everywhere. Nothing is lost by the skip: pathname2url escapes on the
    # character, not on the platform, and the case it guards cannot arise
    # where the name cannot exist.
    @pytest.mark.parametrize(
        "directory",
        (["we?ird"] if os.name != "nt" else []) + ["ha#sh", "sp ace", "per%cent"],
    )
    def test_opens_from_a_path_needing_uri_escaping(
        self, corpus_path, tmp_path, directory
    ):
        # The connection string is a URI, not a path. Unescaped, a directory
        # named "we?ird" ends the path at the "?" and SQLite opens an empty
        # database of the shorter name -- which does not raise, it answers
        # nothing, and the corpus reads as a file with application_id 0.
        import shutil

        target = tmp_path / directory
        target.mkdir()
        path = target / "core.db"
        shutil.copy(corpus_path, path)

        opened = MibCorpus(str(path))

        try:
            assert "FIXTURE-MIB" in opened.modules()

        finally:
            opened.close()

    def test_carries_the_application_id(self, corpus_path):
        import sqlite3

        connection = sqlite3.connect(corpus_path)

        try:
            assert (
                connection.execute("PRAGMA application_id").fetchone()[0]
                == APPLICATION_ID
            )

        finally:
            connection.close()


class TestConformance:
    """pysmi's vectors, run against this reader.

    The vectors are the contract; this is the half of it that lives here. A
    failure means pysnmp reads a corpus differently from how pysmi says it
    should be read, which is exactly the defect neither repository's own tests
    can see.
    """

    def _answer(self, corpus, vector):
        operation = vector["op"]

        # The codec operations take no corpus. They run against *this*
        # module's oid_key, which is a separate implementation from pysmi's
        # on purpose -- reading a corpus is meant to need no pysmi -- so the
        # vectors are what check it against the specification rather than
        # against its own transcription of the specification.
        if operation == "oid_key":
            return oid_key(vector["oid"]).hex()

        if operation == "oid_from_key":
            return oid_from_key(bytes.fromhex(vector["key"]))

        if operation == "subtree_bound":
            return subtree_bound(oid_key(vector["oid"])).hex()

        if operation == "oid_key_order":
            return sorted(vector["oids"], key=oid_key)

        if operation == "oid_key_prefix":
            return oid_key(vector["under"]).startswith(oid_key(vector["oid"]))

        if operation == "oid_key_refuses":
            try:
                oid_key(vector["oid"])

            except Exception:  # noqa: BLE001
                return "refused"

            return "accepted"

        if operation == "meta":
            return corpus.meta(vector["key"])

        if operation == "find_module":
            return corpus.find_module(vector["oid"])

        if operation in ("node", "syntax", "defval", "indices"):
            node = corpus.node(vector["oid"], vector["module"])

            if node is None:
                return None

            if operation == "syntax":
                return node["syntax"]

            if operation == "defval":
                return node["defval"]

            if operation == "indices":
                return node["indices"]

            return {
                key: node[key]
                for key in (
                    "name",
                    "class",
                    "nodetype",
                    "maxaccess",
                    "status",
                    "units",
                    "syntax",
                )
            }

        if operation == "node_by_name":
            node = corpus.node_named(vector["module"], vector["name"])

            return node["oid"] if node else None

        if operation == "next_node":
            node = corpus.next_node(vector["oid"])

            return node["oid"] if node else None

        if operation == "walk":
            out = []
            at = vector["start"]

            for _ in range(vector["count"]):
                node = corpus.next_node(at)

                if node is None:
                    break

                out.append(node["oid"])
                at = node["oid"]

            return out

        if operation == "subtree":
            seen = []

            for node in corpus.subtree(vector["oid"]):
                if node["oid"] not in seen:
                    seen.append(node["oid"])

            return seen

        if operation == "symbol":
            symbol = corpus.symbol(vector["module"], vector["name"])

            return (
                None
                if symbol is None
                else {
                    key: symbol[key]
                    for key in ("class", "status", "displayhint", "type")
                }
            )

        if operation == "same_syntax":
            left = corpus.node(vector["left"][1], vector["left"][0])
            right = corpus.node(vector["right"][1], vector["right"][0])

            return left["syntax"] is right["syntax"]

        if operation == "import_source":
            return corpus.imports_of(vector["module"]).get(vector["name"])

        if operation == "module_field":
            record = corpus.module(vector["module"])
            field = "hash" if vector["field"] == "content_hash" else vector["field"]

            return record[field] if record else None

        raise AssertionError(f"unknown conformance operation {operation!r}")

    @pytest.mark.parametrize("vector", pysmi_conformance.VECTORS, ids=lambda x: x["id"])
    def test_vector(self, corpus, vector):
        assert self._answer(corpus, vector) == vector["expect"], vector["why"]


class TestBuilderUnchangedWithoutACorpus:
    """The compatibility promise, stated as tests.

    Every existing deployment is this configuration. If any of these change,
    an upgrade breaks someone who never asked for a corpus.
    """

    def test_no_corpus_by_default(self):
        assert MibBuilder().getMibCorpus() is None

    def test_modules_still_load_from_sources(self):
        builder = MibBuilder()

        (level,) = builder.importSymbols("SNMP-FRAMEWORK-MIB", "SnmpSecurityLevel")

        assert dict(level.namedValues) == {
            "noAuthNoPriv": 1,
            "authNoPriv": 2,
            "authPriv": 3,
        }

    def test_missing_module_still_raises_mib_not_found(self):
        builder = MibBuilder()

        # loadModule, not loadModules: with no compiler configured the plural
        # form swallows MibNotFoundError, and has since long before any of
        # this. Pinned here because the corpus fallback lives in the singular
        # form, so a change there must not start or stop that happening.
        with pytest.raises(error.MibNotFoundError):
            builder.loadModule("NO-SUCH-MIB")

    def test_loadmodules_still_swallows_a_missing_module(self):
        builder = MibBuilder()

        builder.loadModules("NO-SUCH-MIB")

        assert "NO-SUCH-MIB" not in builder.mibSymbols

    def test_a_corpus_does_not_displace_a_module_on_disk(self, corpus):
        # The corpus is where a module is found when nothing else has it. A
        # module the sources carry keeps resolving from the sources, which is
        # what makes configuring a corpus safe on a running deployment.
        plain = MibBuilder()
        (fromDisk,) = plain.importSymbols("SNMP-FRAMEWORK-MIB", "SnmpSecurityLevel")

        withCorpus = MibBuilder()
        withCorpus.setMibCorpus(corpus)
        (fromBoth,) = withCorpus.importSymbols(
            "SNMP-FRAMEWORK-MIB", "SnmpSecurityLevel"
        )

        assert dict(fromBoth.namedValues) == dict(fromDisk.namedValues)
        assert "corpus:" not in withCorpus._MibBuilder__modSeen["SNMP-FRAMEWORK-MIB"]


class TestBuilderWithACorpus:
    """What opting in adds."""

    @pytest.fixture
    def builder(self, corpus):
        built = MibBuilder()
        built.setMibCorpus(corpus)

        return built

    def test_corpus_is_reported(self, builder, corpus):
        assert builder.getMibCorpus() is corpus

    def test_module_absent_from_sources_resolves_from_the_corpus(self, builder):
        (scalar,) = builder.importSymbols("FIXTURE-MIB", "fixtureScalar")

        assert scalar.getName() == (1, 3, 6, 1, 4, 1, 99999, 1)
        assert scalar.maxAccess == "readonly"
        assert scalar.getUnits() == "seconds"

    def test_table_row_and_column_get_their_classes(self, builder):
        table, row, column = builder.importSymbols(
            "FIXTURE-MIB", "fixtureTable", "fixtureEntry", "fixtureDescr"
        )

        assert type(table).__name__ == "MibTable"
        assert type(row).__name__ == "MibTableRow"
        assert type(column).__name__ == "MibTableColumn"

    def test_row_keeps_its_index_names(self, builder):
        (row,) = builder.importSymbols("FIXTURE-MIB", "fixtureEntry")

        assert row.getIndexNames() == ((0, "FIXTURE-MIB", "fixtureIndex"),)

    def test_textual_convention_becomes_a_class(self, builder):
        (convention,) = builder.importSymbols("FIXTURE-MIB", "FixtureString")

        assert convention.displayHint == "255a"
        assert convention.status == "current"

    def test_column_syntax_resolves_to_the_module_s_own_convention(self, builder):
        convention, column = builder.importSymbols(
            "FIXTURE-MIB", "FixtureString", "fixtureDescr"
        )

        # Not merely an OctetString: a column silently typed as its base
        # renders every value wrong and looks like a device fault.
        assert isinstance(column.syntax, convention)

    def test_enumeration_survives(self, builder):
        (column,) = builder.importSymbols("FIXTURE-MIB", "fixtureBig")

        assert dict(column.syntax.namedValues) == {"up": 1, "down": 2}

    def test_range_constraint_survives(self, builder):
        (column,) = builder.importSymbols("FIXTURE-MIB", "fixtureIndex")

        column.syntax.clone(5)

        with pytest.raises(Exception):
            column.syntax.clone(0)

    def test_module_identity_is_exported_under_the_module_id(self, builder):
        builder.loadModules("FIXTURE-MIB")

        assert builder.mibSymbols["FIXTURE-MIB"][builder.moduleID] is not None

    def test_module_the_corpus_lacks_still_raises(self, builder):
        with pytest.raises(error.MibNotFoundError):
            builder.loadModule("NO-SUCH-MIB")

    def test_loading_twice_is_a_no_op(self, builder):
        builder.loadModules("FIXTURE-MIB")
        builder.loadModules("FIXTURE-MIB")

        assert "FIXTURE-MIB" in builder.mibSymbols

    def test_synthesized_module_can_be_unloaded(self, builder):
        builder.loadModules("FIXTURE-MIB")
        builder.unloadModules("FIXTURE-MIB")

        assert "FIXTURE-MIB" not in builder.mibSymbols

    def test_load_texts_with_a_textless_corpus_is_refused(self, corpus):
        # A caller that asked for descriptions and got a module with none has
        # no way to tell that from a MIB that declares none. With no compiler
        # there is nothing else that could supply them.
        builder = MibBuilder()
        builder.loadTexts = True
        builder.setMibCorpus(corpus)

        with pytest.raises(error.SmiError, match="no texts"):
            builder.loadModule("FIXTURE-MIB")

    def test_attaching_a_textless_corpus_under_load_texts_is_allowed(self, corpus):
        # Attachment is not where this is decided: a compiler may be attached
        # after the corpus is, and refusing here would make a working
        # configuration depend on the order the two were set up in.
        builder = MibBuilder()
        builder.loadTexts = True

        assert builder.setMibCorpus(corpus) is builder
        assert builder.getMibCorpus() is corpus

    def test_type_resolves_when_imports_names_a_module_without_it(
        self, builder, corpus, monkeypatch
    ):
        # A vendor module written against an older revision of a standard
        # module imports a type that revision defined and the current one does
        # not -- BRIDGE-MIB is the recurring case, since RFC 1493 defined
        # MacAddress and RFC 4188 imports it from SNMPv2-TC instead. The
        # corpus carries the newer revision because that is what the ranking
        # rule picks, so following IMPORTS literally fails. Refusing to build
        # the whole module over one type is worse than resolving it from where
        # it actually lives.
        # The type has to be one TYPE_CLASSES does *not* map, or resolution
        # never reaches the IMPORTS step and the test passes whether or not
        # the fallback exists. DisplayString is a TEXTUAL-CONVENTION, so it
        # can only come from a module -- exactly the shape that fails.
        monkeypatch.setattr(
            corpus,
            "imports_of",
            lambda module: (
                {"DisplayString": "NO-SUCH-MIB"}
                if module == "FIXTURE-MIB"
                else corpus.__class__.imports_of(corpus, module)
            ),
        )
        monkeypatch.setattr(
            corpus,
            "node_named",
            lambda module, name: (
                dict(
                    corpus.__class__.node_named(corpus, module, name),
                    syntax={"class": "type", "type": "DisplayString"},
                )
                if (module, name) == ("FIXTURE-MIB", "fixtureDescr")
                else corpus.__class__.node_named(corpus, module, name)
            ),
        )
        monkeypatch.setattr(
            corpus,
            "nodes_of",
            lambda module: [
                dict(node, syntax={"class": "type", "type": "DisplayString"})
                if node["name"] == "fixtureDescr"
                else node
                for node in corpus.__class__.nodes_of(corpus, module)
            ],
        )

        (convention,) = builder.importSymbols("SNMPv2-TC", "DisplayString")
        (column,) = builder.importSymbols("FIXTURE-MIB", "fixtureDescr")

        # Resolved from SNMPv2-TC, where it actually lives, rather than the
        # module IMPORTS named.
        assert isinstance(column.syntax, convention)

    def test_type_that_resolves_nowhere_still_raises(
        self, builder, corpus, monkeypatch
    ):
        # The fallback must not become a silent substitution: a column typed
        # as its base instead of its TEXTUAL-CONVENTION renders every value
        # wrong and looks like a device fault.
        monkeypatch.setattr(
            corpus,
            "symbols_of",
            lambda module: (
                [
                    {
                        "name": "Bogus",
                        "class": "textualconvention",
                        "status": "current",
                        "displayhint": None,
                        "type": {"type": "NoSuchTypeAnywhere", "class": "type"},
                    }
                ]
                if module == "FIXTURE-MIB"
                else corpus.__class__.symbols_of(corpus, module)
            ),
        )

        with pytest.raises(error.SmiError, match="no definition for type"):
            builder.loadModule("FIXTURE-MIB")

    def test_augmenting_row_adopts_the_base_row_index_names(
        self, builder, corpus, monkeypatch
    ):
        # An augmenting row declares AUGMENTS and no INDEX, so without this it
        # gets no index names at all and the runtime cannot decode an instance
        # OID into index values or build one -- while the row looks perfectly
        # well-formed. 1,181 rows in pysnmp/mibs' corpus are this shape and
        # every one of them declares no INDEX.
        augmenting = {
            "module": "FIXTURE-MIB",
            "name": "fixtureAugEntry",
            "oid": "1.3.6.1.4.1.99999.3.1",
            "arcs": (1, 3, 6, 1, 4, 1, 99999, 3, 1),
            "class": "objecttype",
            "nodetype": "row",
            "status": "current",
            "maxaccess": "not-accessible",
            "units": None,
            "syntax": None,
            "defval": None,
            "indices": None,
            "augments": {
                "module": "FIXTURE-MIB",
                "name": "fixtureAugEntry",
                "object": "fixtureEntry",
            },
        }
        monkeypatch.setattr(
            corpus,
            "nodes_of",
            lambda module: (
                [*corpus.__class__.nodes_of(corpus, module), augmenting]
                if module == "FIXTURE-MIB"
                else corpus.__class__.nodes_of(corpus, module)
            ),
        )

        row, base = builder.importSymbols(
            "FIXTURE-MIB", "fixtureAugEntry", "fixtureEntry"
        )

        assert row.getIndexNames() == base.getIndexNames()
        assert row.getIndexNames() == ((0, "FIXTURE-MIB", "fixtureIndex"),)

    def test_augmentation_is_registered_on_the_base_row(
        self, builder, corpus, monkeypatch
    ):
        # A generated module emits both halves: the base row is told it has an
        # augmentation, and the augmenting row adopts its index names. Copying
        # the names alone would leave the base row unaware of the augmentation.
        augmenting = {
            "module": "FIXTURE-MIB",
            "name": "fixtureAugEntry",
            "oid": "1.3.6.1.4.1.99999.3.1",
            "arcs": (1, 3, 6, 1, 4, 1, 99999, 3, 1),
            "class": "objecttype",
            "nodetype": "row",
            "status": "current",
            "maxaccess": "not-accessible",
            "units": None,
            "syntax": None,
            "defval": None,
            "indices": None,
            "augments": {
                "module": "FIXTURE-MIB",
                "name": "fixtureAugEntry",
                "object": "fixtureEntry",
            },
        }
        monkeypatch.setattr(
            corpus,
            "nodes_of",
            lambda module: (
                [*corpus.__class__.nodes_of(corpus, module), augmenting]
                if module == "FIXTURE-MIB"
                else corpus.__class__.nodes_of(corpus, module)
            ),
        )

        (base,) = builder.importSymbols("FIXTURE-MIB", "fixtureEntry")

        assert ("FIXTURE-MIB", "fixtureAugEntry") in base.augmentingRows

    def test_syntax_without_a_type_is_refused(self, builder, corpus, monkeypatch):
        # A KeyError three frames down is the wrong answer for a corpus that
        # is malformed; load_module documents SmiError for exactly this.
        monkeypatch.setattr(
            corpus,
            "nodes_of",
            lambda module: [
                dict(node, syntax={"class": "type"})
                if node["name"] == "fixtureScalar"
                else node
                for node in corpus.__class__.nodes_of(corpus, module)
            ],
        )

        with pytest.raises(error.SmiError, match="carries no type"):
            builder.loadModule("FIXTURE-MIB")

    def test_import_cycle_is_refused_rather_than_recursing(
        self, builder, corpus, monkeypatch
    ):
        # Synthesis resolves imported types through importSymbols, which comes
        # back to loadModule, so a module importing a type from itself by way
        # of another would recurse without limit. It cannot be caught by
        # marking the module loaded first: synthesis exports only when it
        # finishes, so the re-entrant importSymbols would raise
        # MibNotFoundError instead of resolving.
        monkeypatch.setattr(
            corpus,
            "imports_of",
            lambda module: (
                {"CycleType": "FIXTURE-MIB"}
                if module == "FIXTURE-MIB"
                else corpus.__class__.imports_of(corpus, module)
            ),
        )
        monkeypatch.setattr(
            corpus,
            "nodes_of",
            lambda module: [
                dict(node, syntax={"class": "type", "type": "CycleType"})
                if node["name"] == "fixtureScalar"
                else node
                for node in corpus.__class__.nodes_of(corpus, module)
            ],
        )

        with pytest.raises(error.SmiError, match="cycle"):
            builder.loadModule("FIXTURE-MIB")

    def test_load_texts_set_after_attaching_is_still_refused(self, builder):
        # loadTexts is a plain attribute, so a caller can turn it on after the
        # corpus is attached. Checking only at attachment would let that build
        # modules with no DESCRIPTION and say nothing.
        builder.loadTexts = True

        with pytest.raises(error.SmiError, match="no texts"):
            builder.loadModule("FIXTURE-MIB")

    def test_corpus_can_be_removed(self, builder):
        builder.setMibCorpus(None)

        assert builder.getMibCorpus() is None

        with pytest.raises(error.MibNotFoundError):
            builder.loadModule("FIXTURE-MIB")


class TestCorpusWithACompiler:
    """Corpus for the many modules, compiler for the few worth reading.

    A corpus carries no prose and a compiler renders it, so the two together
    are what a MIB browser wants: everything resolves out of the database,
    and the handful of modules whose DESCRIPTION is going on screen are
    rendered from ASN.1 on demand. That only works if a corpus asked for
    texts it does not have steps aside instead of raising.
    """

    COMPILED = (
        '(MibScalar,) = mibBuilder.importSymbols("SNMPv2-SMI", "MibScalar")\n'
        '(Integer32,) = mibBuilder.importSymbols("SNMPv2-SMI", "Integer32")\n'
        "compiledScalar = MibScalar(\n"
        "    (1, 3, 6, 1, 4, 1, 99999, 1), Integer32()\n"
        ').setMaxAccess("readonly")\n'
        'compiledScalar.setDescription("Rendered from ASN.1, prose and all.")\n'
        'mibBuilder.exportSymbols("FIXTURE-MIB", compiledScalar=compiledScalar)\n'
    )

    @pytest.fixture
    def compiler(self, tmp_path):
        class RecordingCompiler:
            """A compiler that records its calls and renders one known module."""

            def __init__(self, destDir):
                self.destDir = destDir
                self.calls = []

            def compile(self, modName, **options):
                self.calls.append((modName, options))

                with open(os.path.join(self.destDir, f"{modName}.py"), "w") as fp:
                    fp.write(TestCorpusWithACompiler.COMPILED)

                return {modName: "compiled"}

        return RecordingCompiler(str(tmp_path))

    @pytest.fixture
    def builder(self, corpus, compiler):
        built = MibBuilder()
        built.setMibCorpus(corpus)
        built.setMibCompiler(compiler, compiler.destDir)

        return built

    def test_texts_send_the_module_to_the_compiler(self, builder, compiler):
        builder.loadTexts = True

        builder.loadModules("FIXTURE-MIB")

        assert compiler.calls == [("FIXTURE-MIB", {"genTexts": True})]

        (scalar,) = builder.importSymbols("FIXTURE-MIB", "compiledScalar")

        assert scalar.getDescription() == "Rendered from ASN.1, prose and all."

    def test_without_texts_the_corpus_answers_and_the_compiler_idles(
        self, builder, compiler
    ):
        # The corpus is the cheap path and stays the default. Nothing is
        # compiled for a module it can already resolve.
        builder.loadModules("FIXTURE-MIB")

        assert compiler.calls == []

        (scalar,) = builder.importSymbols("FIXTURE-MIB", "fixtureScalar")

        assert scalar.getName() == (1, 3, 6, 1, 4, 1, 99999, 1)

    def test_loading_one_module_does_not_reach_the_compiler(self, builder, compiler):
        # loadModule() never compiles, with or without a corpus. Declining
        # turns into MibNotFoundError there, which is what it has always been
        # for a module nothing carries.
        builder.loadTexts = True

        with pytest.raises(error.MibNotFoundError):
            builder.loadModule("FIXTURE-MIB")

        assert compiler.calls == []

    def test_a_module_the_compiler_cannot_render_is_reported(self, builder, compiler):
        builder.loadTexts = True
        compiler.compile = lambda modName, **options: {modName: "missing"}

        with pytest.raises(error.MibNotFoundError, match="compilation error"):
            builder.loadModules("FIXTURE-MIB")

    def test_a_compiled_module_is_what_later_loads_find(self, builder, compiler):
        # The compiler writes into a directory that setMibCompiler() puts on
        # the search path, and sources are searched before the corpus. So a
        # module compiled once for its prose is the copy every later load
        # resolves to, whether or not texts are still wanted -- the corpus does
        # not take it back.
        builder.loadTexts = True
        builder.loadModules("FIXTURE-MIB")
        builder.unloadModules("FIXTURE-MIB")

        builder.loadTexts = False
        builder.loadModules("FIXTURE-MIB")

        assert compiler.calls == [("FIXTURE-MIB", {"genTexts": True})]

        (scalar,) = builder.importSymbols("FIXTURE-MIB", "compiledScalar")

        assert scalar.getDescription() == "Rendered from ASN.1, prose and all."


class TestTrapPath:
    """The access pattern sc4snmp runs on every trap, without a compiler."""

    def test_instance_oid_resolves_to_its_module(self, corpus):
        # A trap carries an instance OID: a column OID plus index arcs, which
        # appears in no MIB at all.
        assert corpus.find_module("1.3.6.1.4.1.99999.2.1.9.1.2.3") == "FIXTURE-MIB"

    def test_unknown_oid_is_a_miss_not_an_error(self, corpus):
        assert corpus.find_module("1.3.6.1.4.1.1") is None

    def test_shadowed_oid_resolves_by_rank_not_by_row_order(self, corpus):
        # Two modules define this OID. The ranked index decides, which is the
        # 1.3.6.1.6.3.1 collision in miniature.
        assert corpus.find_module("1.3.6.1.4.1.99999.1") == "FIXTURE-MIB"

    def test_walk_visits_a_shadowed_oid_once(self, corpus):
        # Once per module and a GETNEXT loop never terminates.
        first = corpus.next_node("1.3.6.1.4.1.99999")
        second = corpus.next_node(first["oid"])

        assert first["oid"] == "1.3.6.1.4.1.99999.1"
        assert second["oid"] == "1.3.6.1.4.1.99999.2"

    def test_walk_off_the_end_is_not_an_error(self, corpus):
        assert corpus.next_node("1.3.6.1.4.1.99999.99") is None

    def test_type_identity_is_shared(self, corpus):
        # The same specification object, not merely an equal one: a reader
        # caching a synthesized class against it must not make two.
        left = corpus.node("1.3.6.1.4.1.99999.1", "FIXTURE-MIB")
        right = corpus.node("1.3.6.1.4.1.99999.2.1.10", "FIXTURE-MIB")

        assert left["syntax"] is right["syntax"]


class TestCompositeResolution:
    """Two corpora searched as one, and the rule that decides which answers.

    The interesting cases are all the same shape: a deployment with the
    distribution's corpus and its own. Which one wins has to follow from what
    the modules state rather than from which was configured first, and a name
    and an OID have to arrive at the same copy.
    """

    def test_modules_is_the_union(self, composite, corpus):
        assert composite.modules() == corpus.modules() | {"PRIVATE-MIB"}

    def test_equal_revisions_leave_a_name_to_the_order(self, composite):
        # The derived corpus is a copy, so both state the same revision for
        # FIXTURE-MIB and there is nothing for the revision rule to separate.
        assert composite.node_named("FIXTURE-MIB", "fixtureScalar") is not None
        assert composite.node_named("FIXTURE-MIB", "privateScalar") is None

    def test_equal_revisions_the_other_way_round(self, reversed_composite):
        assert reversed_composite.node_named("FIXTURE-MIB", "privateScalar") is not None
        assert reversed_composite.node_named("FIXTURE-MIB", "fixtureScalar") is None

    def test_a_module_only_the_second_carries_still_resolves(self, composite):
        assert composite.module("PRIVATE-MIB")["oid"] == PRIVATE_OID

    def test_a_module_no_corpus_carries_is_a_miss(self, composite):
        assert composite.module("NO-SUCH-MIB") is None
        assert composite.nodes_of("NO-SUCH-MIB") == []
        assert composite.symbols_of("NO-SUCH-MIB") == []
        assert composite.imports_of("NO-SUCH-MIB") == {}
        assert composite.symbol("NO-SUCH-MIB", "anything") is None
        assert composite.node_named("NO-SUCH-MIB", "anything") is None

    def test_owner_names_one_corpus_per_module(self, composite):
        assert composite.owner("FIXTURE-MIB") is composite.corpora[0]
        assert composite.owner("PRIVATE-MIB") is composite.corpora[1]
        assert composite.owner("NO-SUCH-MIB") is None

    def test_the_newest_revision_wins_from_the_second_corpus(
        self, corpus_path, newer_path
    ):
        # The rule the whole class turns on. The first corpus carries
        # FIXTURE-MIB and would win on position; the second states a newer
        # revision of it and wins anyway.
        opened = open_corpora([corpus_path, newer_path])

        try:
            assert opened.owner("FIXTURE-MIB") is opened.corpora[1]
            assert opened.node_named("FIXTURE-MIB", "privateScalar") is not None
            assert opened.node_named("FIXTURE-MIB", "fixtureScalar") is None

        finally:
            opened.close()

    def test_an_older_copy_configured_first_is_not_a_downgrade(
        self, corpus_path, older_path
    ):
        # The converse, and the reason position cannot decide: configuring a
        # corpus that happens to carry an older copy of a module would
        # otherwise silently roll that module back.
        opened = open_corpora([older_path, corpus_path])

        try:
            assert opened.owner("FIXTURE-MIB") is opened.corpora[1]
            assert opened.node_named("FIXTURE-MIB", "fixtureScalar") is not None

        finally:
            opened.close()

    def test_both_paths_reach_the_same_copy(self, corpus_path, newer_path):
        # Resolving by name and resolving by OID are one question asked twice.
        # The first corpus anchors this OID and the second owns the module, so
        # an OID path that stopped at the anchor would read the copy the name
        # path rejected.
        opened = open_corpora([corpus_path, newer_path])

        try:
            oid = "1.3.6.1.4.1.99999.2.1.9.1.2.3"
            module = opened.find_module(oid)

            assert module == "FIXTURE-MIB"
            assert opened.owner(module) is opened.corpora[1]

            named = opened.node_named(module, "privateScalar")

            assert opened.node(named["oid"])["name"] == "privateScalar"

        finally:
            opened.close()

    def test_the_losing_corpus_contributes_nothing_to_a_module_it_lost(self, composite):
        # Not "mostly nothing". A module built out of two corpora would define
        # one type twice, and the two classes fail isinstance against each
        # other in a place far from here.
        assert "PrivateOnly" not in composite.imports_of("FIXTURE-MIB")

        names = {x["name"] for x in composite.nodes_of("FIXTURE-MIB")}

        assert "fixtureScalar" in names
        assert "privateScalar" not in names

    def test_a_deeper_anchor_wins_from_a_later_corpus(self, composite):
        # The rule that makes this class necessary. First-match-wins would
        # answer FIXTURE-MIB here, from the anchor seven arcs shorter in the
        # corpus that happens to be searched first.
        assert composite.find_module(f"{PRIVATE_OID}.1.2") == "PRIVATE-MIB"

    def test_a_deeper_anchor_wins_from_an_earlier_corpus_too(self, reversed_composite):
        assert reversed_composite.find_module(f"{PRIVATE_OID}.1.2") == "PRIVATE-MIB"

    def test_equal_anchors_are_separated_by_order_when_undated(self, composite):
        # SMIV1-MIB states no revision, so this contest cannot be decided on
        # one and falls to configured order.
        assert composite.find_module(f"{CONTESTED_OID}.1") == "SMIV1-MIB"

    def test_equal_anchors_the_other_way_round(self, reversed_composite):
        assert reversed_composite.find_module(f"{CONTESTED_OID}.1") == "PRIVATE-MIB"

    def test_equal_anchors_are_separated_by_revision_when_dated(
        self, dated_contest_paths
    ):
        # The same contest with both modules dated. PRIVATE-MIB states 2026
        # against SMIV1-MIB's 2010, so it wins from either position and the
        # order the corpora were configured in stops mattering.
        base, private = dated_contest_paths

        for paths in ([base, private], [private, base]):
            opened = open_corpora(paths)

            try:
                assert opened.find_module(f"{CONTESTED_OID}.1") == "PRIVATE-MIB"

            finally:
                opened.close()

    def test_an_unanchored_oid_is_still_a_miss(self, composite):
        assert composite.find_module("1.3.6.1.4.1.1") is None

    def test_anchor_does_not_chop(self, composite):
        assert composite.anchor(PRIVATE_OID) == "PRIVATE-MIB"
        assert composite.anchor(f"{PRIVATE_OID}.1") is None


class TestCompositeWalking:
    """A walk over several corpora has to look like a walk over one."""

    def _walk(self, store, start, stop):
        found = []
        node = store.next_node(start)

        while node is not None and node["oid"].startswith(stop):
            found.append((node["oid"], node["module"], node["name"]))
            node = store.next_node(node["arcs"])

        return found

    def test_next_node_crosses_into_the_other_corpus(self, composite, corpus):
        # The conformance corpus ends here; the derived one does not.
        assert corpus.next_node("1.3.6.1.4.1.99999.2.1.256") is None

        found = composite.next_node("1.3.6.1.4.1.99999.2.1.256")

        assert (found["oid"], found["module"]) == (PRIVATE_OID, "PRIVATE-MIB")

    def test_a_shadowed_module_is_visited_once(self, composite):
        walked = self._walk(composite, "1.3.6.1.4.1.99999", "1.3.6.1.4.1.99999")
        oids = [x[0] for x in walked]

        assert len(oids) == len(set(oids))
        assert "privateScalar" not in {x[2] for x in walked}

    def test_the_walk_is_ordered(self, composite):
        walked = self._walk(composite, "1.3.6.1.4.1.99999", "1.3.6.1.4.1.99999")
        keys = [oid_key(x[0]) for x in walked]

        assert keys == sorted(keys)

    def test_the_walk_still_ends(self, composite):
        assert composite.next_node("1.3.6.1.4.1.99999.99") is None

    def test_subtree_merges_without_duplicating_a_shadowed_module(self, composite):
        found = composite.subtree("1.3.6.1.4.1.99999")
        seen = [(x["oid"], x["module"]) for x in found]

        assert len(seen) == len(set(seen))
        assert (PRIVATE_OID, "PRIVATE-MIB") in seen
        assert "privateScalar" not in {x["name"] for x in found}

    def test_node_at_an_exact_oid_comes_from_the_owner(self, composite):
        assert composite.node("1.3.6.1.4.1.99999.1")["name"] == "fixtureScalar"
        assert composite.node(PRIVATE_OID)["module"] == "PRIVATE-MIB"

    def test_node_can_still_be_asked_for_one_module_s_definition(self, composite):
        found = composite.node("1.3.6.1.4.1.99999.1", "SHADOW-MIB")

        assert found["name"] == "shadowScalar"

    def test_node_in_a_module_no_corpus_carries(self, composite):
        assert composite.node("1.3.6.1.4.1.99999.1", "NO-SUCH-MIB") is None


class TestCompositeConstruction:
    """What a composite reports about itself, and what it refuses."""

    def test_an_empty_composite_is_refused(self):
        # Every lookup would answer None, which reads as "the corpora do not
        # carry it" rather than as the misconfiguration it is.
        with pytest.raises(error.SmiError):
            CompositeMibCorpus()

    def test_path_is_a_search_path(self, composite, corpus_path, private_path):
        assert composite.path.split(os.pathsep) == [
            os.path.abspath(corpus_path),
            os.path.abspath(private_path),
        ]

    def test_repr_names_the_corpora_in_order(self, composite, private_path):
        assert repr(composite).startswith("CompositeMibCorpus(MibCorpus(")
        assert repr(composite).endswith(
            f"MibCorpus({os.path.abspath(private_path)!r}))"
        )

    def test_meta_answers_from_the_first_corpus_that_has_it(self, composite):
        assert composite.meta("corpus_id") == "pysmi-conformance"

    def test_meta_of_an_unknown_key_is_a_miss(self, composite):
        assert composite.meta("no-such-key") is None

    def test_texts_needs_every_corpus_to_carry_them(self, composite, tmp_path):
        assert composite.loadTexts is False

        half = open_corpora(
            [
                _with_texts(composite.corpora[0].path, str(tmp_path / "texts.db")),
                composite.corpora[1].path,
            ]
        )

        try:
            # One textless corpus in the path means some modules come back
            # with no prose, and which corpus answers is not the caller's
            # choice.
            assert half.loadTexts is False

        finally:
            half.close()

    def test_texts_when_every_corpus_carries_them(self, corpus_path, tmp_path):
        both = open_corpora(
            [
                _with_texts(corpus_path, str(tmp_path / "left.db")),
                _with_texts(corpus_path, str(tmp_path / "right.db")),
            ]
        )

        try:
            assert both.loadTexts is True

        finally:
            both.close()

    def test_close_closes_every_corpus(self, corpus_path, private_path):
        opened = open_corpora([corpus_path, private_path])
        opened.close()

        for one in opened.corpora:
            with pytest.raises(sqlite3.ProgrammingError):
                one.modules()


class TestOpenCorpora:
    """Opening a search path of corpora."""

    def test_one_path_is_not_wrapped(self, corpus_path):
        # A composite of one answers identically and only obscures the corpus
        # in tracebacks and in repr.
        opened = open_corpora([corpus_path])

        try:
            assert isinstance(opened, MibCorpus)

        finally:
            opened.close()

    def test_several_paths_compose(self, corpus_path, private_path):
        opened = open_corpora([corpus_path, private_path])

        try:
            assert isinstance(opened, CompositeMibCorpus)
            assert len(opened.corpora) == 2

        finally:
            opened.close()

    def test_no_paths_is_refused(self):
        with pytest.raises(error.SmiError):
            open_corpora([])

    def test_an_unopenable_corpus_is_reported_not_skipped(self, corpus_path, tmp_path):
        # Skipping it leaves a deployment resolving fewer modules than it
        # asked for, and the only symptom is a MIB that used to be found.
        with pytest.raises(error.SmiError):
            open_corpora([corpus_path, str(tmp_path / "absent.db")])


class TestBuilderCorpusEnvironment:
    """``PYSNMP_MIB_DBS``, which is a thin layer over ``setMibCorpus``."""

    def test_unset_leaves_the_builder_without_a_corpus(self, monkeypatch):
        monkeypatch.delenv("PYSNMP_MIB_DBS", raising=False)

        assert MibBuilder().getMibCorpus() is None

    def test_empty_is_the_same_as_unset(self, monkeypatch):
        monkeypatch.setenv("PYSNMP_MIB_DBS", "")

        assert MibBuilder().getMibCorpus() is None

    def test_one_path_is_opened(self, monkeypatch, corpus_path):
        monkeypatch.setenv("PYSNMP_MIB_DBS", corpus_path)
        builder = MibBuilder()

        try:
            assert isinstance(builder.getMibCorpus(), MibCorpus)

        finally:
            builder.getMibCorpus().close()

    def test_several_paths_keep_the_order_they_were_given(
        self, monkeypatch, corpus_path, private_path
    ):
        monkeypatch.setenv(
            "PYSNMP_MIB_DBS", os.pathsep.join([private_path, corpus_path])
        )
        builder = MibBuilder()

        try:
            assert [x.path for x in builder.getMibCorpus().corpora] == [
                os.path.abspath(private_path),
                os.path.abspath(corpus_path),
            ]

        finally:
            builder.getMibCorpus().close()

    def test_a_missing_corpus_is_an_error_at_construction(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PYSNMP_MIB_DBS", str(tmp_path / "absent.db"))

        with pytest.raises(error.SmiError):
            MibBuilder()

    def test_modules_synthesize_through_the_environment(
        self, monkeypatch, corpus_path, private_path
    ):
        monkeypatch.setenv(
            "PYSNMP_MIB_DBS", os.pathsep.join([corpus_path, private_path])
        )
        builder = MibBuilder()

        try:
            (scalar,) = builder.importSymbols("FIXTURE-MIB", "fixtureScalar")

            assert scalar.getName() == (1, 3, 6, 1, 4, 1, 99999, 1)

        finally:
            builder.getMibCorpus().close()

    def test_precedence_reaches_synthesis(self, monkeypatch, corpus_path, private_path):
        # The same module, from the other corpus, under the descriptor only
        # that corpus gives it.
        monkeypatch.setenv(
            "PYSNMP_MIB_DBS", os.pathsep.join([private_path, corpus_path])
        )
        builder = MibBuilder()

        try:
            (scalar,) = builder.importSymbols("FIXTURE-MIB", "privateScalar")

            assert scalar.getName() == (1, 3, 6, 1, 4, 1, 99999, 1)

        finally:
            builder.getMibCorpus().close()

    def test_the_sources_still_win_over_the_environment(self, monkeypatch, corpus_path):
        # PYSNMP_MIB_DBS adds a place to look, last. A module on disk keeps
        # resolving from disk, which is the whole compatibility story.
        monkeypatch.setenv("PYSNMP_MIB_DBS", corpus_path)
        builder = MibBuilder()

        try:
            builder.loadModule("SNMP-FRAMEWORK-MIB")

            assert "corpus:" not in builder._MibBuilder__modSeen["SNMP-FRAMEWORK-MIB"]

        finally:
            builder.getMibCorpus().close()
