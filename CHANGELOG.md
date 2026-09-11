# Changelog

Generated from the commit history at release time. The narrative history
through 5.x is [published with the documentation](https://pysnmp.github.io/pysnmp/latest/changelog-history.html).

## [6.0.0-rc.11](https://github.com/pysnmp/pysnmp/compare/v6.0.0-rc.10...v6.0.0-rc.11) (2026-09-11)

### ⚠ BREAKING CHANGES

* **secmod:** passwordToKeySHA() returns a different key for the same
passphrase and engine ID. Callers who stored keys derived from it must
re-derive them. The keys it returned before could not be used against any
other implementation.
* **smi:** pysnmp-pysmi is no longer installed with pysnmplib. Code that
relied on pysnmp pulling pysmi in -- importing pysmi directly, or calling
addMibCompiler() -- must install pysnmplib[compile] or depend on pysnmp-pysmi
explicitly. addMibCompiler() already raised SmiError when pysmi was missing, so
what changed is who reaches that path, not what they see on it.
* **smi:** PYSNMP-USM-MIB's pass-phrase columns report not-accessible
where the 2017 rendering left them at MibTableColumn's read-only default:
pysnmpUsmSecretUserName, pysnmpUsmSecretAuthKey, pysnmpUsmSecretPrivKey,
pysnmpUsmKeyAuthLocalized, pysnmpUsmKeyPrivLocalized, pysnmpUsmKeyAuth and
pysnmpUsmKeyPriv. Every one is not-accessible in the module's own MAX-ACCESS
clause, so a manager could read stored authentication and privacy pass-phrases
that the MIB never offered. pysnmp's internal writes are unaffected: they go
through the instrumentation controller with no access-control function, which
is where max-access is enforced.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
* **smi:** SNMP-TARGET-MIB::snmpTargetAddrName and snmpTargetParamsName
report not-accessible where the 2017 copy said read-only. RFC 3413 declares
both IMPLIED INDEX columns and RFC 2578 section 7.3 requires it; nothing
becomes unobtainable, since an index column's value travels in the OID suffix
of every row.
* **smi:** SnmpTagValue and SnmpTagList reject an ASCII CR in a tag.
RFC 3413 section 4.1.1 defines the delimiters as space, tab, CR and LF; the
2017 copy listed tab twice and omitted CR, so "a\rb" was accepted as a single
tag value. Nothing else about the validation changes.
* **smi:** SNMP-FRAMEWORK-MIB::snmpEngineTime has syntax Integer32
rather than a class named SnmpEngineTime. RFC 3411 declares it
SYNTAX INTEGER (0..2147483647) and defines no such textual convention -- the
module's only TCs are SnmpEngineID, SnmpSecurityModel,
SnmpMessageProcessingModel, SnmpSecurityLevel and SnmpAdminString.

Fixes an InetAddress index crash along the way: cloneAsName now clones from
the octets rather than an ascii decode of them, so an InetAddress carrying
raw address bytes no longer fails its DISPLAY-HINT with
"Display format eval failure".

### Features

* **entity:** make v1/v2c a runtime policy rather than a packaging split ([9ab8727](https://github.com/pysnmp/pysnmp/commit/9ab872700b3994ae3ea4a9e7a5777725dfc03943)), closes [#108](https://github.com/pysnmp/pysnmp/issues/108) [#111](https://github.com/pysnmp/pysnmp/issues/111)
* **smi:** delete the last five hand-edited base modules ([98967d2](https://github.com/pysnmp/pysnmp/commit/98967d217adfe348a11605a21b9235d1dae3b0c0)), closes [pysnmp/pysmi#231](https://github.com/pysnmp/pysmi/issues/231) [#232](https://github.com/pysnmp/pysnmp/issues/232) [pysnmp/pysmi#236](https://github.com/pysnmp/pysmi/issues/236) [#198](https://github.com/pysnmp/pysnmp/issues/198)
* **smi:** make pysnmp-pysmi an optional dependency ([0d148fb](https://github.com/pysnmp/pysnmp/commit/0d148fb71185cac2b15b2c49c41f14f24cba4960)), closes [197/#198](https://github.com/197/pysnmp/issues/198) [#196](https://github.com/pysnmp/pysnmp/issues/196)
* **smi:** own MIB runtime behavior and render pysnmp's MIBs from ASN.1 ([7579867](https://github.com/pysnmp/pysnmp/commit/75798679b0462df8c1d9970cfd710da39ba7eae2)), closes [pysnmp/pysmi#236](https://github.com/pysnmp/pysmi/issues/236)
* **smi:** read PYSNMP_MIB_SOURCES for where the ASN.1 is ([d5481be](https://github.com/pysnmp/pysnmp/commit/d5481bee07e40726113d9c5845816882dee1677f)), closes [#144](https://github.com/pysnmp/pysnmp/issues/144)
* **smi:** report which source a module came from, and what it shadowed ([85a7062](https://github.com/pysnmp/pysnmp/commit/85a70623a3c2a7c52f15a237195faea433507b5b))
* **smi:** resolve an unknown OID by loading the module a corpus names ([41d1521](https://github.com/pysnmp/pysnmp/commit/41d1521d47638546b5c170e113377d2857e7795e)), closes [#144](https://github.com/pysnmp/pysnmp/issues/144)
* **smi:** resolve MIBs from a corpus, when asked to ([f90f956](https://github.com/pysnmp/pysnmp/commit/f90f956b3344156d54def6b1adfe90409269178d)), closes [pysnmp/pysnmp#199](https://github.com/pysnmp/pysnmp/issues/199) [pysnmp/pysnmp#144](https://github.com/pysnmp/pysnmp/issues/144) [pysnmp/pysnmp#145](https://github.com/pysnmp/pysnmp/issues/145) [pysnmp/pysnmp#196](https://github.com/pysnmp/pysnmp/issues/196)
* **smi:** search several MIB corpora as one, ordered by precedence ([20f1ef3](https://github.com/pysnmp/pysnmp/commit/20f1ef39550f446921c6f5fa72a0575910fa78f0))

### Bug Fixes

* **deps:** put the pyasn1 floor back on a GA ([278fc80](https://github.com/pysnmp/pysnmp/commit/278fc80d17290180b24e0d0724afb7062f768a2a)), closes [pysnmp/pysmi#236](https://github.com/pysnmp/pysmi/issues/236) [#196](https://github.com/pysnmp/pysnmp/issues/196)
* **secmod:** derive the SHA-1 key from a SHA-1 hash of the passphrase ([515c51b](https://github.com/pysnmp/pysnmp/commit/515c51b3cd4b688421e550b65a9f9fa3df1ff2ba)), closes [#225](https://github.com/pysnmp/pysnmp/issues/225)
* **smi:** drop SNMP-USER-BASED-SM-3DES-MIB ([a27bc4b](https://github.com/pysnmp/pysnmp/commit/a27bc4bdc9af358216adc782d8aae396c8ebe222))
* **smi:** give augmenting rows their index names, and guard the corpus paths ([12ed810](https://github.com/pysnmp/pysnmp/commit/12ed810fd835c625a13a693f2446668a59a2c728)), closes [pysnmp/pysnmp#199](https://github.com/pysnmp/pysnmp/issues/199) [pysnmp/pysnmp#145](https://github.com/pysnmp/pysnmp/issues/145)
* **smi:** let a compiler render the texts a corpus cannot carry ([d0fffd4](https://github.com/pysnmp/pysnmp/commit/d0fffd4b2c5d66cc520514cc54f18686513d19f9)), closes [#217](https://github.com/pysnmp/pysnmp/issues/217)
* **smi:** raise SmiError for a corpus path SQLite cannot open ([6fe848b](https://github.com/pysnmp/pysnmp/commit/6fe848b00f549b147568806c971c27b56616201a))
* **smi:** rank a contested arc by the corpus rule, not by revision alone ([0b9b813](https://github.com/pysnmp/pysnmp/commit/0b9b8133bd1b60a56cbd084787fdb71e5daf3e4d))
* **smi:** resolve a type IMPORTS points at the wrong module for ([d9f1050](https://github.com/pysnmp/pysnmp/commit/d9f1050cda0cdeaf464181acb170e8e92c5c5093)), closes [pysnmp/pysnmp#145](https://github.com/pysnmp/pysnmp/issues/145) [pysnmp/pysnmp#199](https://github.com/pysnmp/pysnmp/issues/199)
* **smi:** satisfy mypy on the corpus reader's two optional paths ([14967ff](https://github.com/pysnmp/pysnmp/commit/14967ff5184b168f63ab1b6d52d71194cb499127))
* **tests:** do not name a directory "we?ird" on a platform that forbids it ([401d73e](https://github.com/pysnmp/pysnmp/commit/401d73e0d8c0589cfdaf2632de2460908badc0f7)), closes [#211](https://github.com/pysnmp/pysnmp/issues/211) [#211](https://github.com/pysnmp/pysnmp/issues/211)
* **tests:** make the corpus suite run in CI instead of skipping itself ([29df876](https://github.com/pysnmp/pysnmp/commit/29df876d75fee1a4be04eb60e6d727ac1da89572)), closes [pysnmp/pysnmp#199](https://github.com/pysnmp/pysnmp/issues/199) [pysnmp/pysmi#184](https://github.com/pysnmp/pysmi/issues/184)

## [6.0.0-rc.10](https://github.com/pysnmp/pysnmp/compare/v6.0.0-rc.9...v6.0.0-rc.10) (2026-09-08)

### ⚠ BREAKING CHANGES

* **entity:** seven INDEX columns of SNMP-VIEW-BASED-ACM-MIB report
not-accessible where the 2017 copy said read-only, per RFC 2578 section 7.3:
vacmAccessContextPrefix, vacmAccessSecurityLevel, vacmAccessSecurityModel,
vacmSecurityModel, vacmSecurityName, vacmViewTreeFamilySubtree and
vacmViewTreeFamilyViewName. Nothing becomes unobtainable -- an index
column's value travels in the OID suffix of every row it appears in. The
fabricated vacmContextStatus column is gone; nothing outside this repository
could have addressed it by name, since it was never in the MIB.
* **smi:** INDEX columns report `not-accessible` where the 2017 base layer
reported `read-only`, which RFC 2578 section 7.3 requires; sixteen columns
across six modules, SNMPv2-MIB::sysORIndex among them. Nothing becomes
unobtainable -- an index column's value travels in the OID suffix of every row
it appears in, so a manager reading the column can read it out of the row
identifier instead. `RFC1213-MIB::TtcpInSegs` (a misspelling of tcpInSegs),
`RFC1158-MIB::snmpInBadTypes` and `RFC1158-MIB::snmpOutReadOnlys` are gone, none
of them declared by any published ASN.1. `SNMPv2-MIB::snmpBasicCompliance` is
now `deprecated` and `snmpObsoleteGroup` `obsolete`, per RFC 3418, and
`RFC1213-MIB::atNetAddress` has syntax `IpAddress` rather than `NetworkAddress`,
the single arm RFC 1155 defines that CHOICE to have.

### Features

* **entity:** create VACM context rows without a column RFC 3415 omits ([e9563a6](https://github.com/pysnmp/pysnmp/commit/e9563a69b8ec500b013f9e5a644b8d75e3264ee2)), closes [#198](https://github.com/pysnmp/pysnmp/issues/198) [#205](https://github.com/pysnmp/pysnmp/issues/205)
* **smi:** delete the 2017 base layer so pysmi's modules are the ones that load ([59e68ba](https://github.com/pysnmp/pysnmp/commit/59e68bad713bbf585fa12b463ee9ce61a24dde9a)), closes [#205](https://github.com/pysnmp/pysnmp/issues/205) [#198](https://github.com/pysnmp/pysnmp/issues/198) [#205](https://github.com/pysnmp/pysnmp/issues/205)
* **smi:** publish and version the MIB module loader contract ([e044df2](https://github.com/pysnmp/pysnmp/commit/e044df24a33b5d25579a30e624295da1478cf0d3)), closes [#197](https://github.com/pysnmp/pysnmp/issues/197)
* **smi:** resolve a module by best match, not by which source answers first ([f380447](https://github.com/pysnmp/pysnmp/commit/f380447264222e1926c916fe031340be0b4aaad4)), closes [#198](https://github.com/pysnmp/pysnmp/issues/198)

### Bug Fixes

* **carrier:** report the family wildcard for an unbound datagram socket ([ab23e50](https://github.com/pysnmp/pysnmp/commit/ab23e505ddb53f8a76cc95c24a078c33333bcfcc)), closes [#173](https://github.com/pysnmp/pysnmp/issues/173)
* **smi:** do not reload a module a newer source appeared for ([b954c75](https://github.com/pysnmp/pysnmp/commit/b954c7579ac70f38cdb1e486668472d6fa94d067)), closes [#198](https://github.com/pysnmp/pysnmp/issues/198)
* **smi:** name the archive a zip-imported MIB module came from ([a9b19ba](https://github.com/pysnmp/pysnmp/commit/a9b19ba2d88aa64e636727e0338159809579fb86)), closes [#198](https://github.com/pysnmp/pysnmp/issues/198)
* **smi:** read a zip archive's directory under its 3.14 name ([62237aa](https://github.com/pysnmp/pysnmp/commit/62237aa1e468c2867293545db4420d990252b93c))

### Performance Improvements

* import the MIB compiler when it is used, not when rfc1902 is imported ([102833b](https://github.com/pysnmp/pysnmp/commit/102833b0cd44c1682ca2e8b07983d8550676a5bb)), closes [#140](https://github.com/pysnmp/pysnmp/issues/140)

## [6.0.0-rc.9](https://github.com/pysnmp/pysnmp/compare/v6.0.0-rc.8...v6.0.0-rc.9) (2026-09-06)

### ⚠ BREAKING CHANGES

* **deps:** pysnmp-pyasn1 must now be >=2.0.0,<3.0.0.

### Bug Fixes

* **debug:** make the debug switch callable whether or not debugging is on ([921b720](https://github.com/pysnmp/pysnmp/commit/921b720e4958de857037d42b53981b355c060f47))
* **deps:** track pysmi and pyasn1 release candidates ([c0a116d](https://github.com/pysnmp/pysnmp/commit/c0a116d555b003f076b4a2df99c04c0b0aca88fb))
* **smi:** make index iteration agree with keys() ([ac4354d](https://github.com/pysnmp/pysnmp/commit/ac4354d986cf76c995fd20c5bbaa65173d769bab))
* **typing:** declare the carrier, mpmod and secmod base attributes ([37bbf9a](https://github.com/pysnmp/pysnmp/commit/37bbf9a52b17f631917ed06fe7605c643adf1283))
* **typing:** give abstract base attributes the type their subclasses use ([6c28cbc](https://github.com/pysnmp/pysnmp/commit/6c28cbc30b2d010b38c7a15cd487786f83e8a550))
* **typing:** stop except: targets shadowing names the function still uses ([8bec4fa](https://github.com/pysnmp/pysnmp/commit/8bec4faba160cbe24d667b9e21117603f79e2cfc))
* **typing:** type-clean the package and enable the mypy pre-commit hook ([bbe8983](https://github.com/pysnmp/pysnmp/commit/bbe898392ffd455d66ae4f7ef1ffff6ea8f8ff8a)), closes [pysnmp/pyasn1#165](https://github.com/pysnmp/pyasn1/issues/165) [#178](https://github.com/pysnmp/pysnmp/issues/178)

### Miscellaneous Chores

* **deps:** bump pysnmp-pyasn1 to 2.0.0 and pysnmp-pysmi to 2.1.0 ([bd3a7e1](https://github.com/pysnmp/pysnmp/commit/bd3a7e13fb9b1fea8ec9511809b9bfd80a8a55ae))

## [6.0.0-rc.8](https://github.com/pysnmp/pysnmp/compare/v6.0.0-rc.7...v6.0.0-rc.8) (2026-09-06)

### Bug Fixes

* **ci:** publish docs from a branch, not a detached HEAD ([9002196](https://github.com/pysnmp/pysnmp/commit/90021961c9aef4d0f135b5af5c8d9055e238a913))

## [6.0.0-rc.7](https://github.com/pysnmp/pysnmp/compare/v6.0.0-rc.6...v6.0.0-rc.7) (2026-09-05)

### Bug Fixes

* **smi:** accept numeric input for integer TCs carrying a DISPLAY-HINT ([7d98e83](https://github.com/pysnmp/pysnmp/commit/7d98e83463ec293d5887ecfcdc55e9bdf4cca5a4)), closes [#150](https://github.com/pysnmp/pysnmp/issues/150)
* **smi:** let transport-address TCs use the TEXTUAL-CONVENTION machinery ([33c91fa](https://github.com/pysnmp/pysnmp/commit/33c91faad6e2ee74e5e33b16acaac82dd322c542)), closes [#155](https://github.com/pysnmp/pysnmp/issues/155)
