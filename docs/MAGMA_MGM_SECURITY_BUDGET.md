# Magma MGM security budget — negative live release gate

Verdict: **NOT_SUITABLE_FOR_CONTINUOUS_TELEMETRY** for the current LightCrypto protocol. No Magma entry/capability/key/ACTIVATE is added. This is an architectural/quantitative finding, not a universal assertion that the standard is unusable.

[RFC8891](https://www.rfc-editor.org/rfc/rfc8891): block64/key256, fixed S-box; not arbitrary28147-89. [RFC9058 §6](https://www.rfc-editor.org/rfc/rfc9058#section-6): with n=S=64, CA≤3(s+4q)^2/2^64; IA≤3(s+4q+l+3)^2/2^64+2/2^64. We conservatively union-bound over all verification attempts and independent keys/epochs. Bounds assume ideal permutation; implementation side channels are separate.

Exact Fraction calculation: `python -m scripts.magma_budget_research --output <new JSON>`. Upper payload1024B AAD+4096B P requires640 blocks/message; real example AAD124B/P83B requires27. Grid: advantage targets2^-32/2^-40/2^-48;1/3/30/300 keys including epochs;16 or1000 total verification attempts/key, q≤attempts. All assumptions and calculated maxima are in magma-budget.json. A q=0 result means **no positive admissible budget under that row**, not permission to invoke the key zero-counter reset.

At target2^-32 and1000 verification attempts, maximum q meeting both aggregate bounds for real example is37/21/6 per key for1/3/30 keys. Under worst-case640 blocks there is no positive q for those settings. The old58 estimate was confidentiality-only, not a sufficient combined release gate. Different packet maxima, attempts, epochs and aggregate target give different values;63-bit nonce uniqueness alone is not the security budget.

Even a few tens of messages require rekey every seconds/minutes at1Hz. Current10000 grant is incompatible, and authenticated secure key delivery/rotation lifecycle is absent. Therefore no live integration, no Magma MQTT graph, no1000-message-per-key benchmark. Isolated public-vector/block/MGM tests of upstream candidates do not imply activation eligibility.
