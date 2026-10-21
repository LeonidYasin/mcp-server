"""Run only in Actions: guard public durable context against silent drift."""
from pathlib import Path
import json
import runpy
import shutil
import pytest
ROOT=Path(__file__).resolve().parents[1]
validate=runpy.run_path(str(ROOT/'scripts/check_handoff.py'))['validate']

def test_handoff_is_navigable_without_private_chat():
    assert validate(ROOT)=={'result':'passed','source_checkpoints':3,'runtime_probe':False}

@pytest.mark.parametrize('change',['runtime','sha','missing','link'])
def test_handoff_rejects_misleading_or_broken_state(tmp_path,change):
    for p in ['AGENTS.md','README.md','ROADMAP.md','docs/ai-handoff.md','docs/chat-progress.md','docs/work-state.json','docs/project-map.md']:
        target=tmp_path/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,target)
    p=tmp_path/'docs/work-state.json';state=json.loads(p.read_text())
    if change=='runtime':state['runtime']['not_a_current_probe']=False
    elif change=='sha':state['source_checkpoints'][0]['sha']='short'
    elif change=='missing':(tmp_path/'docs/ai-handoff.md').unlink()
    elif change=='link':state['source_checkpoints'][0]['evidence_url']='https://example.invalid/branch/main'
    p.write_text(json.dumps(state))
    with pytest.raises(AssertionError):validate(tmp_path)
