# Network identity is not authenticated device identity

Every Shadow record is device_binding=unbound. Network session identity is capture UUID+generation, packet identity is capture UUID+ordinal+frame digest. IP/port/direction never become device_id, key_epoch or sequence_number. No fabricated identity for bad credentials, unsupported transport or rejected AEAD.

Observer has no MQTT password/key registry/HMAC/control key, does not decode TLS or read broker logs/PG identity. Independent laboratory oracle may correlate software sessions later for normal/CV evaluation, but this correlation is not inserted into Shadow storage or predictors. Broker username can corroborate software credentials, not physical hardware origin.

Future binding would need a separate versioned source contract: timed TCP/TLS lifecycle, unambiguous authenticated broker session and topic/credential relationship, optional AEAD accepted identity, clock margins and independent provenance. Ambiguous/lost evidence must remain unbound. This stage does not implement binding confidence heuristics or automatic control.
