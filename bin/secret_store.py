"""Secret-storage infrastructure. Consumers own key/token/password policies.

Returns a requested value in memory. Never prints, persists, syncs, unlocks,
or registers a secret with a remote service.
"""
import json

def read_bitwarden(item, kind, run):
    if not item:raise RuntimeError('Bitwarden 항목 이름이 설정되지 않았습니다.')
    verb='item' if kind=='sshkey' else 'password' if kind=='login' else 'notes'
    result=run(['bw','get',verb,item,'--nointeraction'])
    if result.returncode:raise RuntimeError('Bitwarden 항목 조회 실패. 항목 이름·형식·잠금 상태를 확인하세요.')
    value=result.stdout.rstrip('\n')
    if kind=='sshkey':
        try:value=json.loads(value)['sshKey']['privateKey']
        except (ValueError,KeyError,TypeError):raise RuntimeError('SSH Key 항목 형식이 올바르지 않습니다.') from None
    if not isinstance(value,str) or not value.strip():raise RuntimeError('Bitwarden 항목이 비어 있습니다.')
    return value

