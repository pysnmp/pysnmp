# Changelog

Generated from the commit history at release time. The narrative history
through 5.x is in [CHANGES.md](https://github.com/pysnmp/pysnmp/blob/main/CHANGES.md).

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
