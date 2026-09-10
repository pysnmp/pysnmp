"""Which source a module came from, and which sources were passed over.

Two questions a deployment part-way through the corpus migration has to be able
to ask, and could not:

**Where did this module come from?** `getModulePath` answers with a path, which
is what a person reads and not what a program acts on -- a wheel and a directory
of overrides are both directories, and a corpus is not a path in that sense at
all. `getModuleProvenance` answers `(kind, source_id)`.

**What else could have answered?** A module carried by two sources resolves from
one of them and the other is silently passed over. That is often deliberate --
a local copy placed ahead of the bundled one -- and sometimes a leftover `.py`
that a corpus was supposed to replace, and the two are indistinguishable until
something reports them.

The compatibility promise runs through all of it: a stock install configures
seven shadowed modules before a caller has done anything, because pysnmp carries
its own copies of the engine MIBs and the wheel carries them too. Reporting that
would mean the default install warns, so it is excluded by name and the
exclusion is tested as carefully as the reporting is.
"""

import os
import shutil
import warnings

import pytest
from pysmi.corpus import conformance as pysmi_conformance

from pysnmp.error import PySnmpShadowedModuleWarning
from pysnmp.smi import error
from pysnmp.smi.builder import (
    FRAMEWORK_SHADOW,
    DirMibSource,
    MibBuilder,
    MibSourceKind,
    ZipMibSource,
)
from pysnmp.smi.corpus import MibCorpus, open_corpora

#: A module the engine loads on its own account, carried by both
#: `defaultCoreMibs` and the wheel -- so it is the one to ask about when the
#: question is which of those two answered.
ENGINE_MODULE = "SNMP-FRAMEWORK-MIB"


@pytest.fixture
def mibDir(tmp_path):
    """A directory carrying one real generated module, as a caller's would."""
    source = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "pysnmp",
        "smi",
        "mibs",
        f"{ENGINE_MODULE}.py",
    )

    directory = tmp_path / "mibs"
    directory.mkdir()
    shutil.copy(source, directory / f"{ENGINE_MODULE}.py")

    return str(directory)


@pytest.fixture(scope="module")
def corpusPath(tmp_path_factory):
    """pysmi's conformance corpus, built fresh."""
    directory = tmp_path_factory.mktemp("provenance")

    return pysmi_conformance.build_fixture(str(directory / "conformance.db"))


@pytest.fixture
def corpusModule(corpusPath):
    """A module the conformance corpus carries and no MIB source does."""
    corpus = MibCorpus(corpusPath)

    try:
        modules = sorted(corpus.modules())

    finally:
        corpus.close()

    builder = MibBuilder()
    carried = {name for source in builder.getMibSources() for name in source.listdir()}

    for name in modules:
        if name not in carried:
            return name

    raise AssertionError("the conformance corpus carries nothing a source does not")


class TestModuleProvenance:
    """`(kind, source_id)` for a module that is loaded."""

    def test_engine_modules_come_from_the_overrides(self):
        """The arrangement `defaultCoreMibs` exists to produce.

        pysnmp ships its own copies of the modules the engine needs and
        searches them first, precisely so the wheel's copies cannot displace
        them. That is invisible from a path -- both are directories inside
        site-packages -- and is exactly what provenance is for.
        """
        builder = MibBuilder()
        builder.loadModule(ENGINE_MODULE)

        assert builder.getModuleProvenance(ENGINE_MODULE) == (
            MibSourceKind.OVERRIDE,
            "pysnmp.smi.mibs",
        )

    def test_a_registered_directory_reports_itself(self, mibDir):
        # Ahead of the defaults rather than instead of them: the module IMPORTS
        # from SNMPv2-SMI and ASN1, so replacing the search path outright would
        # fail to load for a reason that has nothing to do with provenance.
        builder = MibBuilder()
        builder.setMibSources(DirMibSource(mibDir), *builder.getMibSources())
        builder.loadModule(ENGINE_MODULE)

        assert builder.getModuleProvenance(ENGINE_MODULE) == (
            MibSourceKind.DIR,
            mibDir,
        )

    def test_an_unloaded_module_has_none(self):
        builder = MibBuilder()

        assert builder.getModuleProvenance(ENGINE_MODULE) is None
        assert builder.getModuleProvenance("NO-SUCH-MIB") is None

    def test_unloading_forgets_where_it_came_from(self):
        """Provenance describes what is loaded, not what once was.

        A module that was unloaded and reloaded may well come back from a
        different source -- that is the whole reason `unloadModules` exists
        alongside best-match selection -- so a record that outlived the load
        would be answering about the wrong copy.
        """
        builder = MibBuilder()
        builder.loadModule(ENGINE_MODULE)
        assert builder.getModuleProvenance(ENGINE_MODULE) is not None

        builder.unloadModules(ENGINE_MODULE)

        assert builder.getModuleProvenance(ENGINE_MODULE) is None

    def test_a_corpus_module_names_the_corpus_that_carried_it(
        self, corpusPath, corpusModule
    ):
        builder = MibBuilder()
        builder.setMibCorpus(MibCorpus(corpusPath))
        builder.loadModule(corpusModule)

        assert builder.getModuleProvenance(corpusModule) == (
            MibSourceKind.DB,
            corpusPath,
        )

    def test_a_composite_names_the_owning_corpus_not_the_search_path(
        self, corpusPath, corpusModule, tmp_path
    ):
        """Which corpus, not which composite.

        A module resolves from exactly one corpus, and naming the whole
        configured path would leave provenance unable to tell a distro corpus
        from a customer one -- which is most of what a deployment wants it
        for.
        """
        second = str(tmp_path / "second.db")
        shutil.copy(corpusPath, second)

        builder = MibBuilder()
        builder.setMibCorpus(open_corpora([corpusPath, second]))
        builder.loadModule(corpusModule)

        kind, sourceId = builder.getModuleProvenance(corpusModule)

        assert kind is MibSourceKind.DB
        assert sourceId in (corpusPath, second)
        assert os.pathsep not in sourceId


class TestSourceKinds:
    """What a source says it is, before any module is loaded from it."""

    def test_a_directory_is_a_directory_and_a_package_is_a_package(self, mibDir):
        assert DirMibSource(mibDir).mibSourceKind is MibSourceKind.DIR
        assert ZipMibSource("pysnmp.smi.mibs").mibSourceKind is MibSourceKind.PKG

    def test_a_substituted_source_keeps_the_kind_it_was_given(self):
        """The wheel is a wheel whether or not it was installed zipped.

        `ZipMibSource.init` hands back a `DirMibSource` for an ordinary
        install, since that is what a wheel unpacks to. Letting the substitute
        take a directory's kind would make the same wheel report `wheel` on a
        zip install and `dir` on a normal one -- an installation detail
        leaking into an answer about configuration.
        """
        source = ZipMibSource("pysnmp.smi.mibs", kind=MibSourceKind.WHEEL)
        opened = source.init()

        assert opened.mibSourceKind is MibSourceKind.WHEEL
        assert opened.sourceId == "pysnmp.smi.mibs"

    def test_the_source_id_survives_the_rewrite_of_the_path(self):
        """`init` rewrites `_srcName`; the id names what the caller registered."""
        source = ZipMibSource("pysnmp.smi.mibs")

        assert source.sourceId == "pysnmp.smi.mibs"

        source.init()

        assert source.sourceId == "pysnmp.smi.mibs"

    def test_a_compiler_destination_is_its_own_kind(self, tmp_path):
        """Compiled output is not a directory a caller chose to register.

        It is a cache the compiler filled, and a deployment auditing where its
        MIBs come from wants to see that difference -- a module resolving from
        `compiled` is one nothing shipped.
        """

        class _Compiler:
            def compile(self, *args, **kwargs):
                return {}

        destination = str(tmp_path / "compiled")
        os.makedirs(destination)

        builder = MibBuilder()
        builder.setMibCompiler(_Compiler(), destination)

        kinds = {
            source.sourceId: source.mibSourceKind for source in builder.getMibSources()
        }

        assert kinds[destination] is MibSourceKind.COMPILED


class TestShadowedModules:
    """What more than one source carries, stated without reading any of it."""

    def test_the_stock_install_shadows_the_engine_modules(self):
        """Reported as fact, because it is one.

        `reportShadowedModules` leaves this out; `shadowedModules` does not.
        The distinction is deliberate -- one answers a question about the
        sources, the other about whether the configuration deserves comment.
        """
        shadowed = MibBuilder().shadowedModules()

        assert ENGINE_MODULE in shadowed
        assert {kind for kind, _ in shadowed[ENGINE_MODULE]} == FRAMEWORK_SHADOW

    def test_a_registered_directory_shadows_the_bundled_copy(self, mibDir):
        builder = MibBuilder()
        builder.addMibSources(DirMibSource(mibDir))

        found = builder.shadowedModules()[ENGINE_MODULE]

        assert (MibSourceKind.DIR, mibDir) in found

    def test_nothing_is_shadowed_when_one_source_carries_it(self, mibDir):
        builder = MibBuilder()
        builder.setMibSources(DirMibSource(mibDir))

        assert builder.shadowedModules() == {}

    def test_a_corpus_shadows_a_source_carrying_the_same_module(
        self, corpusPath, corpusModule, tmp_path
    ):
        """The case the migration creates, and the one an operator gets wrong.

        A deployment adding a corpus keeps its `.py` directory for a while, so
        anything in both is shadowed -- and since `.py` outranks a corpus, the
        corpus is the copy being passed over. That is the opposite of what
        adding one usually means, which is why it has to be reported rather
        than left to be noticed.

        The collision is built rather than looked for: a name-level check reads
        no module, so a file with the right name is the whole of what makes
        this case, and the conformance corpus happens to share no name with the
        default sources.
        """
        directory = tmp_path / "leftovers"
        directory.mkdir()
        (directory / f"{corpusModule}.py").write_text("# a leftover, never loaded\n")

        corpus = MibCorpus(corpusPath)

        try:
            builder = MibBuilder()
            builder.addMibSources(DirMibSource(str(directory)))
            builder.setMibCorpus(corpus)

            found = builder.shadowedModules()[corpusModule]

            assert found == [
                (MibSourceKind.DIR, str(directory)),
                (MibSourceKind.DB, corpusPath),
            ]

        finally:
            corpus.close()

    def test_two_corpora_carrying_one_module_are_both_named(self, corpusPath, tmp_path):
        """The redundant-corpus case, which costs memory and buys nothing."""
        second = str(tmp_path / "second.db")
        shutil.copy(corpusPath, second)

        builder = MibBuilder()
        builder.setMibCorpus(open_corpora([corpusPath, second]))

        shadowed = builder.shadowedModules()
        doubled = [
            name
            for name, found in shadowed.items()
            if sum(1 for kind, _ in found if kind is MibSourceKind.DB) > 1
        ]

        assert doubled
        assert {kind for kind, _ in shadowed[doubled[0]]} >= {MibSourceKind.DB}


class TestReportShadowedModules:
    """When shadowing is said out loud, and how loudly."""

    def test_a_stock_install_says_nothing(self):
        """The compatibility promise, as a test.

        Seven modules are shadowed on every install pysnmp has ever produced.
        A warning here would fire for every user who changed nothing, which is
        both noise and a claim that something is wrong when nothing is.
        """
        builder = MibBuilder()

        with warnings.catch_warnings():
            warnings.simplefilter("error")

            assert builder.reportShadowedModules() == {}

    def test_a_registered_directory_is_warned_about(self, mibDir):
        builder = MibBuilder()
        builder.addMibSources(DirMibSource(mibDir))

        with pytest.warns(PySnmpShadowedModuleWarning) as caught:
            reported = builder.reportShadowedModules()

        assert ENGINE_MODULE in reported
        assert any(ENGINE_MODULE in str(warning.message) for warning in caught)

    def test_the_line_names_the_winner_and_the_losers(self, mibDir):
        builder = MibBuilder()
        builder.addMibSources(DirMibSource(mibDir))

        with pytest.warns(PySnmpShadowedModuleWarning) as caught:
            builder.reportShadowedModules()

        line = next(
            str(warning.message)
            for warning in caught
            if ENGINE_MODULE in str(warning.message)
        )

        # Never "duplicate", never "differs": nothing was read, so nothing
        # about the contents can be claimed.
        assert "shadowing" in line
        assert "duplicate" not in line
        assert mibDir in line

    def test_it_reports_once(self, mibDir):
        """A program loading in several passes should not re-warn each time."""
        builder = MibBuilder()
        builder.addMibSources(DirMibSource(mibDir))

        with pytest.warns(PySnmpShadowedModuleWarning):
            builder.reportShadowedModules()

        with warnings.catch_warnings():
            warnings.simplefilter("error")

            assert builder.reportShadowedModules() != {}

    def test_adding_a_source_arms_it_again(self, mibDir):
        """A source added later can create a collision that did not exist."""
        builder = MibBuilder()

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            builder.reportShadowedModules()

        builder.addMibSources(DirMibSource(mibDir))

        with pytest.warns(PySnmpShadowedModuleWarning):
            builder.reportShadowedModules()

    def test_severity_error_raises_before_anything_is_loaded(self, mibDir):
        """What a deployment sets once it has finished migrating off `.py`."""
        builder = MibBuilder()
        builder.moduleConflictSeverity = "error"
        builder.addMibSources(DirMibSource(mibDir))

        with pytest.raises(error.SmiError) as raised:
            builder.reportShadowedModules()

        assert ENGINE_MODULE in str(raised.value)
        assert builder.mibSymbols == {}

    def test_severity_silent_says_nothing_but_still_answers(self, mibDir):
        builder = MibBuilder()
        builder.moduleConflictSeverity = "silent"
        builder.addMibSources(DirMibSource(mibDir))

        with warnings.catch_warnings():
            warnings.simplefilter("error")

            assert ENGINE_MODULE in builder.reportShadowedModules()

    def test_an_unknown_severity_is_refused(self, mibDir):
        """Refused rather than treated as one of the three.

        A typo defaulting to `silent` turns off a report the deployment asked
        for, and defaulting to `error` breaks one that did not.
        """
        builder = MibBuilder()
        builder.moduleConflictSeverity = "warning"

        with pytest.raises(error.SmiError) as raised:
            builder.reportShadowedModules()

        assert "moduleConflictSeverity" in str(raised.value)

    def test_loading_everything_reports_on_the_way_past(self, mibDir):
        """The one path where the report costs nothing.

        `loadModules()` with no names already enumerates every source, which is
        the whole cost of the report, so that is where it runs. Asserted
        through the severity knob rather than the warning, since loading every
        module in the search path is not something a test should do.
        """
        builder = MibBuilder()
        builder.moduleConflictSeverity = "error"
        builder.setMibSources(DirMibSource(mibDir))
        builder.addMibSources(DirMibSource(mibDir))

        with pytest.raises(error.SmiError) as raised:
            builder.loadModules()

        assert "more than one source" in str(raised.value)


class TestUnchangedWithoutConfiguration:
    """None of this changes what a builder that was configured with nothing does."""

    def test_default_severity_is_warn(self):
        assert MibBuilder.moduleConflictSeverity == "warn"

    def test_loading_a_module_by_name_reports_nothing(self):
        """Only the enumerate-everything path pays for the report.

        A caller loading modules by name never enumerates the sources, and
        making the report happen there anyway would put a `listdir` of every
        source in front of the first `loadModule` of every program.
        """
        builder = MibBuilder()

        with warnings.catch_warnings():
            warnings.simplefilter("error")

            builder.loadModules(ENGINE_MODULE)

        assert builder.getModuleProvenance(ENGINE_MODULE) is not None
