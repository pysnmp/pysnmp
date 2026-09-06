# Changelog

Generated from the commit history at release time. The narrative history
through 5.x is in [CHANGES.md](https://github.com/pysnmp/pysnmp/blob/main/CHANGES.md).

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
