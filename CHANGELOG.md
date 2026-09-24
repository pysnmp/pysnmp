# Changelog

Generated from the commit history at release time. The narrative history
through 5.x is [published with the documentation](https://pysnmp.github.io/pysnmp/latest/changelog-history.html).

## [6.0.0-rc.18](https://github.com/pysnmp/pysnmp/compare/v6.0.0-rc.17...v6.0.0-rc.18) (2026-09-24)

### Bug Fixes

* **deps:** cap pysnmp-pyasn1 below 1.2.0 so 5.x installs again ([05ec299](https://github.com/pysnmp/pysnmp/commit/05ec299e680ada3a5722b8b7c8fd8a45b195cb77))

## [6.0.0-rc.17](https://github.com/pysnmp/pysnmp/compare/v6.0.0-rc.16...v6.0.0-rc.17) (2026-09-21)

### Features

* **smi:** let MIB instrumentation controllers be coroutines ([927e63d](https://github.com/pysnmp/pysnmp/commit/927e63d3c1b5f242e0a97d3676187bc082e77357)), closes [#287](https://github.com/pysnmp/pysnmp/issues/287)
* **smi:** take MIB instrumentation to (varBind, **context) ([666d7a7](https://github.com/pysnmp/pysnmp/commit/666d7a7592bd3eda8714b2cca88148cd7e8a124d)), closes [#287](https://github.com/pysnmp/pysnmp/issues/287) [#279](https://github.com/pysnmp/pysnmp/issues/279)

### Bug Fixes

* **deps:** require pysnmp-pyasn1 >=2.0.5 ([80837eb](https://github.com/pysnmp/pysnmp/commit/80837eb2fadf8f30535ed6a516090d1d0dbf539c)), closes [#334](https://github.com/pysnmp/pysnmp/issues/334) [pysnmp/pyasn1#185](https://github.com/pysnmp/pyasn1/issues/185) [#334](https://github.com/pysnmp/pysnmp/issues/334) [#290](https://github.com/pysnmp/pysnmp/issues/290)
* **deps:** require pysnmp-pyasn1 >=2.0.6 ([8f07227](https://github.com/pysnmp/pysnmp/commit/8f07227ee2ef12f8365e3cb3e6acfc6f05b222e3))
* **proto:** reach a request's execution point once, however it is served ([460bd81](https://github.com/pysnmp/pysnmp/commit/460bd81fbf471957c19460d3e0522015cf8062a7))
* **smi:** pass a legacy walk its original name by position, not by name ([751ba67](https://github.com/pysnmp/pysnmp/commit/751ba670c7154b9efdf4ce0c51001011f055f274)), closes [#328](https://github.com/pysnmp/pysnmp/issues/328)
* **tests:** wait out held operations without asyncio.timeout ([0c0d3c0](https://github.com/pysnmp/pysnmp/commit/0c0d3c0728fc6fb69a4b76c2b2b5825300f4500e))
* **tools:** name the libraries in the comparison table when runs disagree ([512d4ca](https://github.com/pysnmp/pysnmp/commit/512d4ca6e1b9b1eb73351c8b6434b40c95760965))

## [6.0.0-rc.16](https://github.com/pysnmp/pysnmp/compare/v6.0.0-rc.15...v6.0.0-rc.16) (2026-09-20)

### Features

* **carrier:** add SNMP over TCP, RFC 3430 ([6162a63](https://github.com/pysnmp/pysnmp/commit/6162a635f3eae8bd0f78810f0d4baeae8586833e)), closes [#273](https://github.com/pysnmp/pysnmp/issues/273)
* **carrier:** report a transport failure the sender can no longer see ([9308d0f](https://github.com/pysnmp/pysnmp/commit/9308d0fc961ec3ca7be3fb43dd4bcaad4324fce4))
* **entity:** give SnmpEngine dispatcher lifecycle and context managers ([4c484d9](https://github.com/pysnmp/pysnmp/commit/4c484d9a8ea8b110fcb03137c303a9d0e659bd4d)), closes [#277](https://github.com/pysnmp/pysnmp/issues/277) [#275](https://github.com/pysnmp/pysnmp/issues/275)
* **hlapi:** add subtree-bounded walk_cmd and bulk_walk_cmd ([0f9f994](https://github.com/pysnmp/pysnmp/commit/0f9f9942455219f16b02707926e1be8195c94747)), closes [#277](https://github.com/pysnmp/pysnmp/issues/277) [#256](https://github.com/pysnmp/pysnmp/issues/256)
* **hlapi:** make the high-level API snake_case, deprecating camelCase ([42d0726](https://github.com/pysnmp/pysnmp/commit/42d07268467b427672ca9a86ec7e79e908fa1f86)), closes [#277](https://github.com/pysnmp/pysnmp/issues/277)
* **proto:** read an Opaque-wrapped float as a number ([651f3f8](https://github.com/pysnmp/pysnmp/commit/651f3f82729741738172d6b023fed4fb23152c90)), closes [#286](https://github.com/pysnmp/pysnmp/issues/286)
* **secmod:** add Diffie-Hellman USM key management (RFC 2786) ([72929be](https://github.com/pysnmp/pysnmp/commit/72929be63c69633d64bf164c631c64e7ad479542)), closes [PKCS#3](https://github.com/pysnmp/PKCS/issues/3) [#280](https://github.com/pysnmp/pysnmp/issues/280)
* **smi:** export NetworkAddress from SNMPv2-SMI ([652a1ce](https://github.com/pysnmp/pysnmp/commit/652a1ced67266fb0e17c357bcf4c26666972c1dc))
* **smi:** separate name-resolution from value-casting failures ([1aaf828](https://github.com/pysnmp/pysnmp/commit/1aaf828cfd96ec4a03f57efb760a651bfb4b0f02)), closes [#252](https://github.com/pysnmp/pysnmp/issues/252)

### Bug Fixes

* **app:** order notification var-binds without duplicating them ([52be1da](https://github.com/pysnmp/pysnmp/commit/52be1daae08d73b7700890400b9f7e8a68a508b1)), closes [#260](https://github.com/pysnmp/pysnmp/issues/260)
* **carrier:** keep the IPv6 scope ID on the way to sendto() ([87cdb76](https://github.com/pysnmp/pysnmp/commit/87cdb76d967afc8c305d69e80258b5d3515bd494)), closes [#251](https://github.com/pysnmp/pysnmp/issues/251)
* **carrier:** refuse a transport bound to a different event loop ([61c8b12](https://github.com/pysnmp/pysnmp/commit/61c8b1269fc5ae8b6a35b5d7589db004df5c0aee))
* **ci:** install file(1) in the DH agent build stage ([0031949](https://github.com/pysnmp/pysnmp/commit/0031949dc603bc0d0d3531bb90fde4b322fcb320))
* **ci:** the test group needs ruff, because a test renders MIB modules ([a39dfda](https://github.com/pysnmp/pysnmp/commit/a39dfda51a8002b93433534e96a411204ad302c4))
* **entity:** keep an engine importable on PyPy, and split a test group ([ab6ba2b](https://github.com/pysnmp/pysnmp/commit/ab6ba2b3759db25099cf2951caf4ecaf84a56d97))
* **hlapi:** drop a failed lookup where it is picked up, not from its callback ([77d285b](https://github.com/pysnmp/pysnmp/commit/77d285b7af5c4fa5db2c9655796e3035c2686f20))
* **hlapi:** keep an in-flight address lookup when a caller is cancelled ([9be6460](https://github.com/pysnmp/pysnmp/commit/9be6460cf611104c2674a7603ba604e425e756e7)), closes [#311](https://github.com/pysnmp/pysnmp/issues/311)
* **hlapi:** make the clock fine enough to measure the timeout asked for ([764551d](https://github.com/pysnmp/pysnmp/commit/764551d2e49b5a57f29ee80e2cbf29523f61bd04)), closes [#289](https://github.com/pysnmp/pysnmp/issues/289)
* **hlapi:** re-register a v3 user whose credentials changed ([b342465](https://github.com/pysnmp/pysnmp/commit/b3424659411950357b3f1047126ecca7620237f5)), closes [#261](https://github.com/pysnmp/pysnmp/issues/261)
* **hlapi:** stop transport target DNS from stalling the event loop ([ba657c8](https://github.com/pysnmp/pysnmp/commit/ba657c8278b81a596a4fc50b81de9e851d61a938)), closes [#270](https://github.com/pysnmp/pysnmp/issues/270)
* **proto:** reject a short v2c notification instead of raising IndexError ([b18a13e](https://github.com/pysnmp/pysnmp/commit/b18a13e7d1b0118cc754699cac07b2d0c8a0af21)), closes [#266](https://github.com/pysnmp/pysnmp/issues/266)
* **proto:** render NetworkAddress as an address, not a Choice dump ([f862d2e](https://github.com/pysnmp/pysnmp/commit/f862d2e1a94d7b72e7a2940335b641fea546308e)), closes [#271](https://github.com/pysnmp/pysnmp/issues/271)
* **proto:** wrap Counter32, Counter64 and TimeTicks at their ceiling ([6a184cb](https://github.com/pysnmp/pysnmp/commit/6a184cb365c96c8139c1a3de69ee829400ee3a11)), closes [#257](https://github.com/pysnmp/pysnmp/issues/257)
* **secmod:** derive the key before the SET and bound DH key generation ([d193a7c](https://github.com/pysnmp/pysnmp/commit/d193a7c1a17fe151d271a6a06d5d57503f7e13cc))
* **secmod:** draw a fitting DH public value, and draw it off the loop ([44342d7](https://github.com/pysnmp/pysnmp/commit/44342d7770bedf59d54a876e03577a9de42131b5)), closes [#316](https://github.com/pysnmp/pysnmp/issues/316)
* **secmod:** follow the snake_case rename in the new DH tests ([66371ef](https://github.com/pysnmp/pysnmp/commit/66371ef4a62ae5cf19623ae7a5bad008ac8fe117))
* **secmod:** stop padding AES-CFB128 ciphertext ([595eb73](https://github.com/pysnmp/pysnmp/commit/595eb731c940daa319a7b5461aef7c0edb7a748a)), closes [#262](https://github.com/pysnmp/pysnmp/issues/262)
* **smi:** answer noSuchInstance for an uninitialised scalar ([5194fbe](https://github.com/pysnmp/pysnmp/commit/5194fbed032042f470d4cf8d66617fa9f7b8fb43)), closes [#263](https://github.com/pysnmp/pysnmp/issues/263)
* **smi:** cache compiled MIBs where the platform says, not in ~/.pysnmp ([dd55d68](https://github.com/pysnmp/pysnmp/commit/dd55d68189fe80707b404c740c6180ffe767b303)), closes [#253](https://github.com/pysnmp/pysnmp/issues/253)
* **smi:** derive the engine ID from platform.node(), not os.uname() ([708353a](https://github.com/pysnmp/pysnmp/commit/708353a88fc4cb9f9a5cb6fb424416688db21881)), closes [#269](https://github.com/pysnmp/pysnmp/issues/269)
* **smi:** do not end a walk over one row whose index will not decode ([1cf042f](https://github.com/pysnmp/pysnmp/commit/1cf042fc8e969ded1d1948ba202aab998348d15f)), closes [#252](https://github.com/pysnmp/pysnmp/issues/252) [#255](https://github.com/pysnmp/pysnmp/issues/255) [#255](https://github.com/pysnmp/pysnmp/issues/255)
* **smi:** encode InetAddress table indices with their length prefix ([e4787a8](https://github.com/pysnmp/pysnmp/commit/e4787a86e5e9029f1d583a883a7e2f4f17dbd416)), closes [#259](https://github.com/pysnmp/pysnmp/issues/259)
* **smi:** key the index cache on the instance OID it was asked about ([9720093](https://github.com/pysnmp/pysnmp/commit/9720093f7e94b32c1d8193eb0b0313e582f69b75)), closes [#255](https://github.com/pysnmp/pysnmp/issues/255) [#252](https://github.com/pysnmp/pysnmp/issues/252) [#255](https://github.com/pysnmp/pysnmp/issues/255)
* **smi:** report a missing MIB from loadModules() with no compiler ([adc8ef6](https://github.com/pysnmp/pysnmp/commit/adc8ef65653864fa8b26d44656255586009d0c91)), closes [#264](https://github.com/pysnmp/pysnmp/issues/264)
* **smi:** report an InetAddressType that contradicts its address ([57f49ce](https://github.com/pysnmp/pysnmp/commit/57f49ce1a5a6d4cab873cc5347c77886d65d1df1)), closes [#259](https://github.com/pysnmp/pysnmp/issues/259) [#268](https://github.com/pysnmp/pysnmp/issues/268)
* **smi:** resolve a bare InetAddress index without an InetAddressType ([89f66b6](https://github.com/pysnmp/pysnmp/commit/89f66b6f704b059423f7f036f927cb8b72ef49bd))
* **smi:** return the column default from setValue(None) ([b5b3c8e](https://github.com/pysnmp/pysnmp/commit/b5b3c8e2ad949572e93e1a21c76c799a737badd4)), closes [#258](https://github.com/pysnmp/pysnmp/issues/258)
* **smi:** serve a namespace package as a MIB source ([ae8ec7e](https://github.com/pysnmp/pysnmp/commit/ae8ec7e1e1c5ac11e30f667c83067355212a7e9f)), closes [#265](https://github.com/pysnmp/pysnmp/issues/265)
* **smi:** skip the index cache on values pyasn1 refuses to hash ([377df5a](https://github.com/pysnmp/pysnmp/commit/377df5ac3164f8a43f561dff2b0c55a423612b8c)), closes [#282](https://github.com/pysnmp/pysnmp/issues/282)
* **smi:** stop ignoreErrors gating whether a value can be represented ([bde8138](https://github.com/pysnmp/pysnmp/commit/bde8138cb53faef6753ca2a1147e85346a938690)), closes [#252](https://github.com/pysnmp/pysnmp/issues/252)

### Performance Improvements

* **secmod:** find a fitting DH public value by walking, not redrawing ([718ffba](https://github.com/pysnmp/pysnmp/commit/718ffba705cad427e4a4142ce76285cf3be727a1)), closes [#324](https://github.com/pysnmp/pysnmp/issues/324) [#324](https://github.com/pysnmp/pysnmp/issues/324)
* **smi:** bisect once in nextKey instead of scanning the keys twice ([4d63ba7](https://github.com/pysnmp/pysnmp/commit/4d63ba7a11dfca63128c6c85708222bc666050d4)), closes [#267](https://github.com/pysnmp/pysnmp/issues/267)

## [6.0.0-rc.15](https://github.com/pysnmp/pysnmp/compare/v6.0.0-rc.14...v6.0.0-rc.15) (2026-09-18)

### Bug Fixes

* **smi:** render the MIB modules target configuration needs ([323d7e0](https://github.com/pysnmp/pysnmp/commit/323d7e0fd501325b0ada40f916ea0b69dce343ff))

## [6.0.0-rc.14](https://github.com/pysnmp/pysnmp/compare/v6.0.0-rc.13...v6.0.0-rc.14) (2026-09-17)

## [6.0.0-rc.13](https://github.com/pysnmp/pysnmp/compare/v6.0.0-rc.12...v6.0.0-rc.13) (2026-09-16)

## [6.0.0-rc.12](https://github.com/pysnmp/pysnmp/compare/v6.0.0-rc.11...v6.0.0-rc.12) (2026-09-14)

### Features

* **smi:** read a schema 2 corpus, and answer where a module came from ([aa25837](https://github.com/pysnmp/pysnmp/commit/aa2583775b8e30cfb63ac689df90e26e9e7e894b))

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
