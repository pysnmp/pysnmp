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
    MibCorpus,
    oid_from_key,
    oid_key,
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
        # no way to tell that from a MIB that declares none.
        builder = MibBuilder()
        builder.loadTexts = True

        with pytest.raises(error.SmiError, match="no texts"):
            builder.setMibCorpus(corpus)

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
