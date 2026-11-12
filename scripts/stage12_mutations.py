"""Retain earlier behavioral mutations and add persistent IPC/budget failure cases."""
from scripts import kuz_mutations
runner=kuz_mutations.runner
runner.MUTATIONS += [
 ('discard_complete_response_on_stderr_eof','src/kuz_worker.py',"selector.unregister(self.process.stderr) # EOF may race a complete stdout response","raise ProviderUnavailable('EOF incorrectly treated as failure')",'test_kuz_worker.py::test_stderr_eof_does_not_discard_complete_valid_response'),
 ('worker_mixes_device_responses','src/kuz_worker.py',"if response[:8]!=identity:","if False:",'test_kuz_worker.py::test_malformed_worker_never_returns_plaintext[wrong_id]'),
 ('provider_returns_plaintext_on_error','src/kuz_provider.py',"if status!=0:raise ProviderUnavailable('Kuznyechik provider internal failure')","if status!=0:return response[1:]",'test_kuz_worker.py::test_malformed_worker_never_returns_plaintext[plaintext_on_error]'),
 ('missing_backend_silent_ascon','src/crypto_profiles.py',"return PROVIDERS[profile][0](key,nonce,ad,plaintext)","try:return PROVIDERS[profile][0](key,nonce,ad,plaintext)\n    except __import__('src.kuz_provider',fromlist=['ProviderUnavailable']).ProviderUnavailable:return _ascon_encrypt(key[:16],nonce,ad,plaintext)",'test_kuz_worker.py::test_dispatch_missing_backend_never_falls_back'),
 ('repeat_grant_burns_budget_again','src/device_control/server.py',"        return old['body']","        from src.kuz_usage import reserve\n        reserve(c,device,d['key_epoch'],body['message_id'],old['body']['data']['first_sequence'],old['body']['data']['last_sequence'])\n        return old['body']",'test_kuz_integration.py::test_reservation_is_atomic_idempotent_crash_burned_and_bounded'),
]
if __name__=='__main__':runner.main()
