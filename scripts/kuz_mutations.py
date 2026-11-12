"""Stage11 behavioral mutations, retaining the earlier control/security mutations."""
from scripts import control_mutations as runner
runner.MUTATIONS += [
 ('unknown_ascon_fallback','src/crypto_profiles.py',"    _parameters(profile,key,nonce,ad,plaintext)","    if type(profile) is not str or profile not in PROFILES:profile=ASCON\n    _parameters(profile,key,nonce,ad,plaintext)",'test_provider_dispatch.py::test_unknown_never_reaches_ascon'),
 ('mgm_ignores_tag_failure','src/kuz_provider.py',"if status in [1,2] and len(result.stdout)==1:raise ValueError('MGM authentication/parameter rejection')","if status==1:return b'unauthenticated'\n    if status==2:raise ValueError('MGM authentication/parameter rejection')",'test_kuz_provider.py::test_authentication_failure_returns_no_plaintext[tag]'),
 ('ignore_mgm_budget','src/kuz_usage.py',"if row['reserved_invocations']+count>row['max_invocations'] or row['reserved_blocks']+320*count>row['max_blocks']:","if False:",'test_kuz_integration.py::test_reservation_is_atomic_idempotent_crash_burned_and_bounded'),
 ('reuse_aes_key_for_kuz','src/telemetry.py',"key=entry['key_hex'] if profile==ASCON else entry.get('telemetry_keys',{}).get(algorithm)","key=entry['key_hex'] if profile==ASCON else entry.get('telemetry_keys',{}).get('AES-128-GCM' if profile==KUZ else algorithm)",'test_kuz_integration.py::test_mgm_malformed_aad_is_controlled'),
 ('legacy_ascon_broken','src/crypto_profiles.py',"return ascon_encrypt(key, nonce, ad, plaintext, 'Ascon-AEAD128')","return b'broken legacy ciphertext'",'test_provider_dispatch.py::test_legacy_ascon_dispatch_preserves_external_known_answer'),
 ('legacy_aes_broken','src/crypto_profiles.py',"lambda k,n,a,p: AESGCM(k).encrypt(n,p,a)","lambda k,n,a,p: b'broken ciphertext'",'test_aes_profiles.py::test_cavp_cavs_14_count_zero'),
]
if __name__=='__main__':runner.main()
