# Track B Authority Location Supersession (R1)

## Authority Decision

- **CTO Decision**: `B_SUPERSEDE_PRIOR_PIN_AND_ADOPT_CANONICAL_DOCS_RESEARCH`
- **Former Locator**: `/Users/kelvin/VibeCoding-WorkSpace/`
- **Canonical Authority Location**: `docs/research/`
- **Location Authority**: Superseded
- **Content SHA-256 Authority**: Retained and unchanged

---

## Pinned Content SHA-256 Identities

The three exact SHA-256 values were reverified and remain strictly identical:

| Artifact Basename | Canonical Authority Location | Pinned SHA-256 Hash | Status |
| :--- | :--- | :--- | :--- |
| `B649_TRACK_B_EH01_EH10_PARAMETER_LOCK_PROPOSAL_R1.md` | `docs/research/B649_TRACK_B_EH01_EH10_PARAMETER_LOCK_PROPOSAL_R1.md` | `76629e97f0f7a44848075da6e615f9c946e2b80dedb23bc3d77a6e67104fd094` | VERIFIED |
| `B649_TRACK_B_EH02_PARAMETER_LOCK_PROPOSAL_R1.md` | `docs/research/B649_TRACK_B_EH02_PARAMETER_LOCK_PROPOSAL_R1.md` | `69e03026ce40962cfed8a8295336918edc6f6db8d3d6f0f3f5a487a1bfc9262b` | VERIFIED |
| `B649_TRACK_B_EH02_DATA_AUTHORITY_AND_PARAMETER_LOCK_RESOLUTION_R1.md` | `docs/research/B649_TRACK_B_EH02_DATA_AUTHORITY_AND_PARAMETER_LOCK_RESOLUTION_R1.md` | `76aef07bedb10d51ab0446170c116bf9b5ffee8fc3b5c36ad8e13c14f46daae7` | VERIFIED |

---

## Sealed Surfaces and Preregistration Integrity

1. **Sealed Preregistration Artifacts & Sealing Generators**:
   Sealed preregistration artifacts and sealing generators (`tools/hash_preregistration_eh01_eh10_b649.py`, `tools/hash_preregistration_eh02_b649.py`) are intentionally byte-untouched.

2. **Historical Path Strings**:
   Historical path strings participate in frozen preregistration canonical-byte hashes and remain untouched.

3. **Additive Authority Metadata**:
   Old locator retirement is additive authority metadata only, not an in-place seal rewrite.

4. **Frozen Preregistration Hashes**:
   - EH01–EH10 B649 Preregistration Hash: `f12ef1314e4fd6cadcd28154b332f04afa46bb9593a23733708540ae3302c8f7`
   - EH02 B649 Preregistration Hash: `45a7ddd6a1409a1da65bc347beed6cbb34efa73291910f91b4a3e59b98446045`

5. **Dangling Locators**:
   Historical references containing `/Users/kelvin/VibeCoding-WorkSpace/` across past sealed research notes remain preserved as immutable historical artifacts; dangling locator repair is deferred and not claimed as repaired by this publication.
