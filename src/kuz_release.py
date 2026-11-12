"""Explicit isolated validation authorization, never global production activation."""
import os,re

def validation_enabled():
    return (os.environ.get('APP_ENV')=='test' and os.environ.get('LCM_KUZ_VALIDATION_AUTHORIZATION')=='1'
            and re.fullmatch(r'lcm-(?:stage11-kuznyechik|stage12-crypto-research|stage13-policy)-[a-z0-9-]{1,18}',os.environ.get('LCM_LAB_PROJECT','')) is not None)

def allow_validation():
    if not validation_enabled():raise ValueError('Kuznyechik restricted to explicitly authorized isolated validation lab')
    from src.kuz_provider import self_test
    if not self_test():raise ValueError('MGM known-answer readiness failed')
