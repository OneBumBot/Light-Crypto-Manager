"""Security boundaries with public fixture keys; no simulated device ACK in E2E."""
from datetime import datetime,timezone,timedelta
import copy,uuid,hashlib
import pytest
from src.device_control.protocol import message,seal,open_message,topic,validate
from src.device_control.state import DeviceState
from src.crypto_profiles import ASCON,AES
from src.telemetry import canonical

KEY=bytes(range(32));ACK_KEY=bytes(range(32,64))


def command(phase='PREPARE',sequence=1,transition=None):
    cid=str(uuid.uuid4());tid=transition or str(uuid.uuid4())
    return message('alpha','command',dict(command_id=cid,transition_id=tid,correlation_id=tid,command_type='set_profile',phase=phase,
        requested_profile=AES,source_version='admin-v1',controller_identity='lcm-manual-controller',profile_config_version=1,
        key_reference=AES+':1',command_epoch=1,command_sequence=sequence),message_id=cid)


def conf():return dict(command_key=KEY.hex(),status_key=ACK_KEY.hex(),capabilities=[ASCON,AES],registry=dict(telemetry_keys={'AES-128-GCM':bytes(range(100,116)).hex()}))


def test_control_authenticated_direction_and_device():
    b=command();raw=seal(b,KEY,'controller')
    assert open_message(raw,KEY,'controller','alpha',topic('alpha','controller'))==b
    for key,direction,device,t in [(ACK_KEY,'controller','alpha',topic('alpha','controller')),(KEY,'device','alpha',topic('alpha','controller')),(KEY,'controller','beta',topic('beta','controller'))]:
        with pytest.raises(ValueError):open_message(raw,key,direction,device,t)
    bad=raw.replace(b'PREPARE',b'ACTIVATE')
    with pytest.raises(ValueError):open_message(bad,KEY,'controller','alpha',topic('alpha','controller'))


@pytest.mark.parametrize('field,value',[
    ('schema_version',True),('schema_version',1),('message_id','bad-id'),('device_id','../alpha'),('kind','shell'),
    ('created_at','NaN'),('expires_at','2001-01-01T00:00:00+00:00'),('extra',1),
])
def test_strict_contract(field,value):
    b=command();b[field]=value
    with pytest.raises((ValueError,TypeError)):seal(b,KEY,'controller')


@pytest.mark.parametrize('field,value',[('command_sequence',True),('command_epoch',0),('requested_profile','unknown'),('command_type','execute'),('controller_identity','intruder'),('phase','APPLIED'),('key_reference','aes-key-other'),('profile_config_version',True),('source_version','research')])
def test_strict_command_fields(field,value):
    b=command();b['data'][field]=value
    with pytest.raises(ValueError):validate(b)


def test_duplicate_json_and_nonfinite_rejected():
    raw=seal(command(),KEY,'controller')
    for bad in [raw.replace(b'"domain":',b'"domain":"x","domain":'),raw.replace(b'"schema_version":2',b'"schema_version":NaN')]:
        with pytest.raises(ValueError):open_message(bad,KEY,'controller','alpha',topic('alpha','controller'))


def test_device_prepare_activate_retry_and_restart(tmp_path):
    path=tmp_path/'device.db';s=DeviceState(path,'alpha',1,initialize=True);c=conf();prepare=command()
    ready=s.execute(prepare,c);assert s.read()['profile']==ASCON
    assert s.execute(prepare,c)==ready
    activate=command('ACTIVATE',2,prepare['data']['transition_id'])
    applied=s.execute(activate,c);assert s.read()['profile']==AES
    assert s.execute(activate,c)==applied
    s.close();s=DeviceState(path,'alpha',1)
    assert s.read()['profile']==AES and s.execute(activate,c)==applied
    conflict=copy.deepcopy(activate);conflict['message_id']=str(uuid.uuid4());conflict['data']['command_id']=conflict['message_id']
    with pytest.raises(ValueError):s.execute(conflict,c)
    with pytest.raises(ValueError):s.execute(command('PREPARE',1),c)
    s.close()


def test_no_activate_without_prepare_or_foreign_transition(tmp_path):
    s=DeviceState(tmp_path/'device.db','alpha',1,initialize=True)
    with pytest.raises(ValueError):s.execute(command('ACTIVATE',1),conf())
    p=command();s.execute(p,conf())
    with pytest.raises(ValueError):s.execute(command('ACTIVATE',2),conf())
    assert s.read()['profile']==ASCON;s.close()


def test_missing_state_fails_closed_and_unsupported_does_not_apply(tmp_path):
    with pytest.raises(ValueError):DeviceState(tmp_path/'missing.db','alpha',1)
    s=DeviceState(tmp_path/'device.db','alpha',1,initialize=True);c=conf();c['capabilities']=[ASCON]
    raw=s.execute(command(),c)
    assert open_message(raw,ACK_KEY,'device','alpha',topic('alpha','device'))['data']['result']=='UNSUPPORTED'
    assert s.read()['profile']==ASCON;s.close()


def test_device_state_process_lock(tmp_path):
    p=tmp_path/'state.db';s=DeviceState(p,'alpha',1,initialize=True)
    with pytest.raises(BlockingIOError):DeviceState(p,'alpha',1)
    s.close()


def test_monotonic_replay_gap_rejected(tmp_path):
    s=DeviceState(tmp_path/'state.db','alpha',1,initialize=True)
    high=command(sequence=100);s.execute(high,conf())
    lower=command('ACTIVATE',50,high['data']['transition_id'])
    with pytest.raises(ValueError):s.execute(lower,conf())
    assert s.read()['profile']==ASCON;s.close()


def test_authenticated_claimed_device_mismatch():
    import hmac,json
    from src.device_control.protocol import DOMAIN
    body=command()
    envelope=dict(domain=DOMAIN,direction='controller',topic=topic('beta','controller'),body=body)
    raw=canonical(dict(**envelope,mac=hmac.new(KEY,canonical(envelope),hashlib.sha256).hexdigest()))
    with pytest.raises(ValueError):open_message(raw,KEY,'controller','beta',topic('beta','controller'))


def test_independent_mac_vector():
    # Canonical envelope expected MAC generated independently with OpenSSL dgst
    # 3.6.5 SHA256/HMAC, public key bytes(range(32)), not Python seal().
    import json
    n=datetime(2026,11,10,tzinfo=timezone.utc);u='00000000-0000-4000-8000-000000000001'
    b=message('alpha','command',dict(command_id=u,transition_id=u,correlation_id=u,command_type='set_profile',phase='PREPARE',requested_profile=AES,
        source_version='admin-v1',controller_identity='lcm-manual-controller',profile_config_version=1,key_reference=AES+':1',command_epoch=1,command_sequence=1),now=n,message_id=u)
    assert json.loads(seal(b,KEY,'controller',now=n))['mac']=='17c0f0e26d8a35a9d819ed363fdf5e056547ed7559454fa23407c8db7964b3a8'


def test_prior_positive_command_epoch_rejected(tmp_path):
    # Positive previous epoch, not merely invalid epoch zero or a future epoch.
    s=DeviceState(tmp_path/'state.db','alpha',2,initialize=True)
    with pytest.raises(ValueError):s.execute(command(),conf())
    assert s.read()['seq']==0 and s.read()['profile']==ASCON;s.close()


@pytest.mark.parametrize('mac',['é'*64,'a','00'*33,None,123])
def test_malformed_mac_is_bounded_value_error(mac):
    import json
    envelope=json.loads(seal(command(),KEY,'controller'));envelope['mac']=mac
    with pytest.raises(ValueError):open_message(canonical(envelope),KEY,'controller','alpha',topic('alpha','controller'))
