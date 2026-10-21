"""Static durable-context guard; no app import, network or remote execution."""
import json
from pathlib import Path
import re

def validate(root):
    state=json.loads((root/'docs/work-state.json').read_text())
    assert state['schema']==1 and state['repository']=='LeonidYasin/mcp-server'
    assert re.fullmatch('[0-9a-f]{40}',state['snapshot_main_sha'])
    assert state['runtime']['not_a_current_probe'] is True
    assert state['related_rooms']['not_a_server_deployment'] is True
    assert state['verification']['runtime']=='GitHub Actions only'
    assert len(state['unresolved'])>=4
    assert len({c['id'] for c in state['source_checkpoints']})==3
    for c in state['source_checkpoints']:
        assert re.fullmatch('[0-9a-f]{40}',c['sha'])
        assert '/blob/'+c['sha']+'/' in c['evidence_url']
        assert c['sha'] in (root/'docs/chat-progress.md').read_text()
    for name in state['read_first']:
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        assert (root/name).is_file()
    agents=(root/'AGENTS.md').read_text()
    assert 'special password' in agents and 'expected_head_sha' in agents
    for f in ['README.md','ROADMAP.md']:
        assert 'docs/ai-handoff.md' in (root/f).read_text()
    return {'result':'passed','source_checkpoints':3,'runtime_probe':False}

if __name__=='__main__':
    print('HANDOFF QA PASS: '+json.dumps(validate(Path(__file__).resolve().parents[1]),sort_keys=True))
