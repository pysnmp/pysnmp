# GitHub Copilot Instructions

## Priority Guidelines

When generating code for this repository:

1. **Version Compatibility**: Always detect and respect the exact versions of languages, frameworks, and libraries used in this project
2. **Context Files**: Prioritize patterns and standards defined in the `.github/copilot` directory
3. **Codebase Patterns**: When context files don't provide specific guidance, scan the codebase for established patterns
4. **Architectural Consistency**: Maintain the layered, RFC-mirrored architectural style and established module boundaries
5. **Code Quality**: Prioritize maintainability, performance, security, and testability in all generated code

## Technology Version Detection

Before generating code, scan the codebase to identify:

1. **Language Versions**: Detect the exact versions of programming languages in use
   - Examine `pyproject.toml` for the Python version constraint (`python = "^3.10"`)
   - Python Support from 3.10 to 3.14 is allowed, but do not use features introduced in versions later than the detected version or earlier than 3.10
   - The codebase uses f-strings (e.g. `pysnmp/error.py`, `pysnmp/entity/engine.py`) — f-strings are permitted
   - The `match` statement (3.10+) is permitted; do not introduce `type` aliases (3.12+) or other post-3.10 syntax

2. **Framework Versions**: Identify the exact versions of all frameworks
   - Build system: uv with hatchling (`hatchling>=1.0.0`, declared in `pyproject.toml` `[build-system]`)
   - Package metadata lives in `pyproject.toml` under the standard PEP 621 `[project]` table; the distribution name is `pysnmplib` (version `5.0.24`)
   - The in-package version is duplicated in `pysnmp/__init__.py` as `__version__ = '5.0.24'` — keep both in sync when bumping versions
   - Never suggest features not available in the detected framework versions

3. **Library Versions**: Note the exact versions of key libraries and dependencies
   - Runtime dependencies (from `pyproject.toml`): `pysnmp-pysmi >=1.0.4,<3.0.0`, `pycryptodomex >=3.11.0,<4.0.0`, `pysnmp-pyasn1 >=1.1.3,<2.0.0`
   - Dev dependencies (from `pyproject.toml` `[project.optional-dependencies]`): `sphinx >=4.3.0,<5.0.0`, `pytest >=6.2.5,<9.0.0`, `codecov >=2.1.12,<3.0.0`, `pytest-codecov >=0.4.0,<1.0.0`
   - Generate code compatible with these specific versions
   - The project depends on the **pysnmp-pyasn1** fork, not upstream pyasn1. Import from `pyasn1.type`, `pyasn1.codec.ber`, `pyasn1.error`, and `pyasn1.compat.octets` as seen throughout `pysnmp/proto/` and `pysnmp/smi/`
   - Cryptography uses **pycryptodomex** (the `Cryptodome` namespace), imported under `pysnmp/proto/secmod/` for USM auth/priv protocols
   - Never use APIs or features not available in the detected versions

## Context Files

Prioritize the following files in `.github/copilot` directory (if they exist):

- **architecture.md**: System architecture guidelines
- **tech-stack.md**: Technology versions and framework details
- **coding-standards.md**: Code style and formatting standards
- **folder-structure.md**: Project organization guidelines
- **exemplars.md**: Exemplary code patterns to follow

## Codebase Scanning Instructions

When context files don't provide specific guidance:

1. Identify similar files to the one being modified or created
2. Analyze patterns for:
   - Naming conventions
   - Code organization
   - Error handling
   - Logging approaches
   - Documentation style
   - Testing patterns

3. Follow the most consistent patterns found in the codebase
4. When conflicting patterns exist, prioritize patterns in newer files or files with higher test coverage
5. Never introduce patterns not found in the existing codebase

## Architecture

This is a pure-Python SNMP v1/v2c/v3 engine. The package layout mirrors the SNMP RFC architecture and must be respected when adding or modifying code:

- `pysnmp/proto/` — Protocol layer: ASN.1/BER type definitions (`rfc1155.py`, `rfc1902.py`, `rfc1905.py`), message processing models (`mpmod/`), security models (`secmod/`), access control (`acmod/`), PDU API (`api/v1.py`, `api/v2c.py`), and proxy conversion (`proxy/rfc2576.py`). Files are named after the RFC they implement.
- `pysnmp/smi/` — SMI layer: MIB builder/compiler (`builder.py`, `compiler.py`), instrumentation (`instrum.py`), MIB view (`view.py`), and the high-level SMI types in `smi/rfc1902.py` (`ObjectIdentity`, `ObjectType`, `NotificationType`). Bundled MIB modules live in `smi/mibs/`.
- `pysnmp/entity/` — SNMP entity: `engine.py` (`SnmpEngine`, the central stateful coordinator per RFC 3412), `config.py` (LCD configuration helpers), `observer.py` (execution-context observer), and `rfc3413/` (SNMP applications: `cmdgen`, `cmdrsp`, `ntforg`, `ntfrcv`, `context`).
- `pysnmp/carrier/` — Transport layer: `base.py` (`AbstractTransportDispatcher`, `TimerCallable`), with `asyncio/` as the sole I/O backend. Datagram transports (`dgram/udp.py`, `dgram/udp6.py`, `dgram/unix.py`) live under `asyncio/`.
- `pysnmp/hlapi/` — High-level API: `auth.py` (`CommunityData`, `UsmUserData`), `context.py` (`ContextData`), `transport.py` (`AbstractTransportTarget`), `varbinds.py` (varbind construction/resolution), `lcd.py` (LCD configurators). The `asyncio/` subpackage (with `asyncio/sync/` for the blocking facade) exposes `getCmd`, `nextCmd`, `setCmd`, `bulkCmd`, `sendNotification`.
- `pysnmp/error.py` — Base `PySnmpError` exception. All other error modules (`proto/error.py`, `proto/errind.py`, `smi/error.py`, `carrier/error.py`) derive from it.

### Architectural rules

- **`SnmpEngine` is the only stateful object.** All SNMP operations take a `SnmpEngine` instance; in multithreaded environments each thread must have its own (see the class docstring in `pysnmp/entity/engine.py`).
- **Keep RFC boundaries intact.** New protocol behavior goes in `proto/` under the appropriate `rfcXXXX.py` or `mpmod/`/`secmod/` submodule named after the RFC. SNMP application behavior goes in `entity/rfc3413/`.
- **HLAPI is a thin facade.** `pysnmp/hlapi/` delegates to `pysnmp/entity/rfc3413/` and `pysnmp/proto/api/`; do not implement protocol logic in the hlapi layer.
- **Single I/O backend.** The asyncore backend has been removed. All transport and hlapi functionality uses `asyncio/` only. The default synchronous API lives in `hlapi/asyncio/sync/`.
- **Module-level singletons are used for stateless services.** Examples: `vbProcessor = CommandGeneratorVarBinds()` and `lcd = CommandGeneratorLcdConfigurator()` at the top of `hlapi/asyncio/cmdgen.py`. Follow this pattern for new stateless service objects.

## Code Quality Standards

### Maintainability
- Write self-documenting code with clear naming
- Follow the naming and organization conventions evident in the codebase
- Follow established patterns for consistency
- Keep functions focused on single responsibilities
- Limit function complexity and length to match existing patterns

### Performance
- Follow existing patterns for memory and resource management
- Use the `pysnmp/cache.py` `Cache` class (limited-size, usage-based eviction) for per-engine caches; see also `pysnmp/proto/cache.py`, `pysnmp/proto/mpmod/cache.py`, `pysnmp/proto/secmod/cache.py`
- Match existing patterns for handling computationally expensive operations
- Follow established patterns for asynchronous operations
- Apply caching consistently with existing patterns
- Optimize according to patterns evident in the codebase

### Security
- Follow existing patterns for input validation
- Apply the same sanitization techniques used in the codebase
- USM key material handling must go through `pysnmp/proto/secmod/rfc3414/localkey.py` (`hashPassphrase`, `passwordToKey`, `localizeKey`) — never roll your own key derivation
- Encryption/decryption must subclass `AbstractEncryptionService` (`proto/secmod/rfc3414/priv/base.py`) and authentication must subclass `AbstractAuthenticationService` (`proto/secmod/rfc3414/auth/base.py`)
- Follow established authentication and authorization patterns (USM in `secmod/rfc3414/`, VACM in `acmod/rfc3415.py`)
- Handle sensitive data (community strings, auth/priv keys) according to existing patterns — never log them

### Testability
- Follow established patterns for testable code
- Match dependency injection approaches used in the codebase (services receive `snmpEngine` and pull context via `snmpEngine.getUserContext()` / `snmpEngine.setUserContext()`)
- Apply the same patterns for managing dependencies
- Follow established mocking and test double patterns
- Match the testing style used in existing tests

## Documentation Requirements

- Follow the exact documentation format found in the codebase
- Match the NumPy-style docstrings used throughout `pysnmp/hlapi/` and `pysnmp/proto/rfc1902.py`: a one-line summary, `Parameters`, `Other Parameters`, `Returns`, `Raises`, `Warnings` (when relevant), and `Examples` sections
- Reference RFCs with the `:RFC:` Sphinx role exactly as existing docstrings do, e.g. `` :RFC:`3414#section-6` ``
- Reference other pysnmp objects with `:py:class:` / `:py:obj:` / `:py:func:` roles, e.g. `` :py:class:`~pysnmp.hlapi.SnmpEngine` ``
- Include runnable `Examples` doctest-style blocks in public API docstrings (see `CommunityData`, `ContextData`, `Integer32` for the established style)
- Document parameters, returns, and exceptions in the same style
- Match class-level documentation style and content

## Testing Approach

### Unit Testing
- Match the exact structure and style of existing unit tests
- Follow the same naming conventions for test classes and methods
- Use the same assertion patterns found in existing tests
- Apply the same mocking approach used in the codebase
- Follow existing patterns for test isolation

### Integration Testing
- Follow the same integration test patterns found in the codebase
- Match existing patterns for test data setup and teardown
- Use the same approach for testing component interactions
- Follow existing patterns for verifying system behavior

### Examples as smoke tests
- `runtests.sh` executes the scripts under `examples/` as the project's integration smoke tests. When adding or changing hlapi behavior, add or update a matching example script in `examples/hlapi/<backend>/...` so `runtests.sh` continues to cover it.

## Python Guidelines
- Detect and adhere to the specific Python version in use (3.10+, per `pyproject.toml`)
- Follow the same import organization found in existing modules: stdlib first, then third-party (`pyasn1.*`, `Cryptodome.*`), then `pysnmp.*` submodules. See `pysnmp/entity/config.py` and `pysnmp/smi/rfc1902.py` for the canonical ordering.
- Use `from pysnmp.proto.rfc1902 import *` / `from pysnmp.smi.rfc1902 import *` style re-exports in hlapi modules (as done in `pysnmp/hlapi/__init__.py` and `pysnmp/hlapi/asyncio/__init__.py`); define `__all__` in modules that intend a public surface (e.g. `pysnmp/hlapi/auth.py`, `pysnmp/proto/rfc1902.py`).
- Type hints are **not** used in this codebase. Do not introduce them unless asked; match the untyped style of existing modules.
- Apply the same error handling patterns found in existing code:
  - Raise `pysnmp.error.PySnmpError` (or a subclass from `proto/error.py`, `smi/error.py`, `carrier/error.py`, `proto/errind.py`) for library-level errors.
  - `ProtocolError` and its subclasses are raised for SNMP v3 protocol failures; `SmiError` and its subclasses for MIB/SMI failures; `CarrierError` for transport failures; `ErrorIndication` subclasses (`proto/errind.py`) for SNMP error-indication values.
  - Use the `StatusInformation` / `MibOperationError` kwargs-bag pattern (see `proto/error.py`, `smi/error.py`) when passing structured error context.
- Follow the same module organization patterns: one RFC or concern per file, abstract base class first (`Abstract*`), then concrete implementations.

## Logging and Debugging

- Use the `pysnmp.debug` module's flag-based logging pattern, **not** `print()` or direct `logging` calls:
  ```python
  from pysnmp import debug

  debug.logger & debug.flagMP and debug.logger("prepareOutgoingMessage: new msgID %s" % msgID)
  ```
- The available flags are defined in `pysnmp/debug.py`: `flagIO`, `flagDsp`, `flagMP`, `flagSM`, `flagBld`, `flagMIB`, `flagIns`, `flagACL`, `flagPrx`, `flagApp`, `flagAll`. Choose the flag matching the subsystem you're working in (`flagMP` for message processing, `flagSM` for security, `flagMIB`/`flagBld`/`flagIns` for SMI, `flagACL` for access control, `flagIO` for transport, `flagApp` for SNMP applications).
- The `debug.logger & flag and debug.logger(...)` short-circuit pattern is mandatory — it avoids formatting cost when the flag is disabled.
- Use `%`-style formatting in debug messages to match the dominant style in `proto/secmod/`, `proto/mpmod/`, and `entity/rfc3413/`; f-strings are acceptable in newer files (as in `entity/engine.py`) but prefer consistency with the surrounding file.

## Error Handling Patterns

- The base exception is `pysnmp.error.PySnmpError` (`pysnmp/error.py`); it captures `sys.exc_info()` as `.cause` and appends `caused by ...` to the message. Let this base class carry cause context rather than reimplementing it.
- SNMP v3 protocol errors derive from `ProtocolError(PySnmpError, PyAsn1Error)` in `proto/error.py`; SMI errors derive from `SmiError(PySnmpError, PyAsn1Error)` in `smi/error.py`; transport errors derive from `CarrierError(PySnmpError)` in `carrier/error.py`.
- `ErrorIndication` (`proto/errind.py`) is a separate `Exception` hierarchy for SNMP error-indication values; instances are compared by string value and carry a `.prettyPrint()`-style description.
- Abstract base classes raise `error.ProtocolError('method not implemented')` for unimplemented methods (see `proto/mpmod/base.py`, `proto/secmod/base.py`). Follow this when adding new abstract methods.
- HLAPI functions return the `(errorIndication, errorStatus, errorIndex, varBinds)` tuple rather than raising for SNMP-level errors; raise `PySnmpError` only for usage/configuration errors. See `hlapi/asyncio/cmdgen.py:getCmd`.

## HLAPI Conventions

- The four canonical command-generator functions are `getCmd`, `nextCmd`, `setCmd`, `bulkCmd`, plus `sendNotification` for notifications. Each takes `(snmpEngine, authData, transportTarget, contextData, *varBinds, **options)` and is `async` in `hlapi/asyncio/`.
- `isEndOfMib = lambda x: not cmdgen.getNextVarBinds(x)[1]` is the shared end-of-mib sentinel check; reuse it rather than re-deriving.
- Varbind construction goes through `CommandGeneratorVarBinds` / `NotificationOriginatorVarBinds` (`hlapi/varbinds.py`); MIB resolution goes through `ObjectType.resolveWithMib(mibViewController, ignoreErrors=False)`.
- LCD configuration goes through `CommandGeneratorLcdConfigurator` / `NotificationOriginatorLcdConfigurator` (`hlapi/lcd.py`), which cache per-`SnmpEngine` state under `snmpEngine.setUserContext(...)`. Do not call `entity/config.py` functions directly from hlapi code — use the configurators.

## Version Control Guidelines

- Follow Semantic Versioning patterns as applied in the codebase
- The version appears in **two** places that must stay in sync: `pyproject.toml` (`version = "..."` under `[project]`) and `pysnmp/__init__.py` (`__version__ = '...'`). The `__init__.py` also derives `version` (tuple) and `majorVersionId` — preserve that derivation logic when bumping.
- Match existing patterns for documenting breaking changes in `CHANGELOG.md` (Revision-header sections with bulleted notes)
- Follow the same approach for deprecation notices

## General Best Practices

- Follow naming conventions exactly as they appear in existing code:
  - `CamelCase` for classes (including SNMP type subclasses like `Integer32`, `OctetString`, `CommunityData`, `UsmUserData`, `SnmpEngine`).
  - `lowerCamelCase` for functions, methods, and variables (e.g. `getCmd`, `sendNotification`, `addV3User`, `snmpEngineID`).
  - `UPPER_SNAKE_CASE` for module-level constants and flag bitmasks (e.g. `flagIO`, `snmpUDPDomain`, `usmHMACSHAAuthProtocol`).
  - `__doubleLeading` name-mangling for private attributes on classes (e.g. `self.__cache`, `self.__observers` in `entity/observer.py`, `carrier/base.py`).
- Match code organization patterns from similar files
- Apply error handling consistent with existing patterns
- Follow the same approach to testing as seen in the codebase
- Match logging patterns from existing code (the `debug.logger & flag` pattern)
- Use the same approach to configuration as seen in the codebase (LCD via `entity/config.py`, `SnmpEngine` user context)

## Project-Specific Guidance

- Scan the codebase thoroughly before generating any code
- Respect existing architectural boundaries without exception — proto/ for protocol, smi/ for MIB/SMI, entity/ for SNMP entity, carrier/ for transport, hlapi/ for the high-level facade
- Match the style and patterns of surrounding code
- When in doubt, prioritize consistency with existing code over external best practices
- When adding a new RFC implementation, name the file after the RFC number and place it in the appropriate submodule (`proto/`, `proto/mpmod/`, `proto/secmod/`, `entity/rfc3413/`)
- When adding a new SNMP type, subclass the corresponding `pyasn1.type.univ.*` class in `proto/rfc1902.py` (v2c) or `proto/rfc1155.py` (v1) and declare it in `__all__`
- When adding a new transport, subclass `AbstractTransport` (`carrier/base.py`) under `carrier/asyncio/dgram/`, and expose the domain constant via `entity/config.py`
- Examples under `examples/` are executable and run by `runtests.sh`; keep them working and follow their header-comment + `asyncio.run()` structure when adding new ones