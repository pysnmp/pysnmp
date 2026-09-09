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

import pytest

from pysnmp.smi import error
from pysnmp.smi.builder import MibBuilder
from pysnmp.smi.corpus import (
    APPLICATION_ID,
    SCHEMA_VERSION,
    MibCorpus,
    oid_from_key,
    oid_key,
    subtree_bound,
)

pysmi_conformance = pytest.importorskip(
    "pysmi.corpus.conformance",
    reason="the conformance fixture is published by pysmi, a dev dependency",
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


class TestOidKey:
    """The encoding the whole file format's ordering rests on.

    pysmi writes these keys and pysnmp reads them, and neither imports the
    other, so the two implementations agreeing is a thing to test rather than
    a thing to assume.
    """

    @pytest.mark.parametrize(
        "oid", ["1", "1.3.6", "1.3.6.1.4.1.9", "2.0", "1.3.6.1.4.1.4294967295"]
    )
    def test_round_trips(self, oid):
        assert oid_from_key(oid_key(oid)) == oid

    def test_accepts_arcs_as_well_as_text(self):
        assert oid_key((1, 3, 6)) == oid_key("1.3.6")

    def test_byte_order_is_numeric_order(self):
        # 1.3.10 below 1.3.9 is what string comparison gets wrong; 1.3.256 is
        # what one byte per arc gets wrong.
        oids = ["1.3.6", "1.3.6.1", "1.3.7", "1.3.9", "1.3.10", "1.3.256", "2.0"]

        assert sorted(oids, key=oid_key) == sorted(
            oids, key=lambda x: tuple(int(a) for a in x.split("."))
        )

    def test_prefix_encodes_to_byte_prefix(self):
        assert oid_key("1.3.6.1").startswith(oid_key("1.3.6"))

    def test_parent_sorts_before_children(self):
        assert oid_key("1.3.6") < oid_key("1.3.6.0")

    def test_subtree_bound_brackets_the_subtree(self):
        low = oid_key("1.3.6")
        high = subtree_bound(low)

        assert low <= oid_key("1.3.6.1.4.1.99") < high
        assert not low <= oid_key("1.3.7") < high

    def test_subtree_bound_carries_past_a_full_byte(self):
        key = oid_key("1.255")

        assert subtree_bound(key) > oid_key("1.255.1")

    @pytest.mark.parametrize("bad", ["", "1.3.six", "not an oid"])
    def test_rejects_what_is_not_an_oid(self, bad):
        with pytest.raises(error.SmiError):
            oid_key(bad)

    def test_rejects_arc_out_of_range(self):
        with pytest.raises(error.SmiError):
            oid_key("1.4294967296")

    def test_agrees_with_pysmi(self):
        # The two implementations are separate on purpose -- importing pysmi
        # to read a file whose point is that it needs no pysmi would defeat
        # the layering -- so they have to be checked against each other.
        from pysmi.corpus.db import oid_key as writer_key

        for oid in ("1.3.6.1.2.1.2.2.1.2", "1.3.256.9.10", "2.0", "1"):
            assert oid_key(oid) == writer_key(oid)


class TestCorpusOpen:
    """What a corpus refuses to be opened as."""

    def test_missing_file(self, tmp_path):
        with pytest.raises(error.SmiError, match="no MIB corpus"):
            MibCorpus(str(tmp_path / "absent.db"))

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
        # no way to tell that from a MIB that declares none.
        builder = MibBuilder()
        builder.loadTexts = True

        with pytest.raises(error.SmiError, match="no texts"):
            builder.setMibCorpus(corpus)

    def test_corpus_can_be_removed(self, builder):
        builder.setMibCorpus(None)

        assert builder.getMibCorpus() is None

        with pytest.raises(error.MibNotFoundError):
            builder.loadModule("FIXTURE-MIB")


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
