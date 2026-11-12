import json
import pytest
from src.device_control.research_journal import ResearchJournal


def test_opt_in_append_and_bound(tmp_path):
    path=tmp_path/'events.jsonl'
    j=ResearchJournal(path,maximum=100)
    for i in range(102):j.record('scheduled',count=1)
    assert j.exhausted
    j.close()
    records=[json.loads(s) for s in path.read_text().splitlines()]
    assert len(records)==100 and path.stat().st_mode&0o077==0
    other=ResearchJournal(path,maximum=100)
    assert other.boot!=records[0]['boot']
    other.record('start');assert other.exhausted;other.close()
    assert len(path.read_text().splitlines())==100


@pytest.mark.parametrize('n',[None,True,99,100001,1.5,'100'])
def test_invalid_bound(n):
    with pytest.raises(ValueError):ResearchJournal(maximum=n)


def test_disabled_has_no_files():
    j=ResearchJournal();j.record('formed',sequence=1);j.close()
    assert j.file is None and j.count==0
