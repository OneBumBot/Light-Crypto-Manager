"""Presentation mutations, served only to one Chromium test page; no deployed edits."""
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable output exists')
    with tempfile.TemporaryDirectory(prefix='stage9-dom-mutations-') as folder:
        tmp=Path(folder);baseline_cmd=[sys.executable,'-m','scripts.check_stage9_dom','--directory',str(a.directory),'--output',str(tmp/'baseline.json')]
        baseline=subprocess.run(baseline_cmd,capture_output=True,text=True,timeout=80)
        if baseline.returncode:raise RuntimeError('DOM baseline failed: '+baseline.stdout+baseline.stderr)
        source=Path('src/web/static/js/monitoring.js').read_text();results=[]
        mutations=[('ui_ack_as_effective',"['Verified effective profile',profile(d.effective_profile)]","['Verified effective profile',profile(d.reported_profile || d.effective_profile)]"),
            ('ui_stale_as_recent',"status(d.status));", "status('recent'));"),
            ('ui_mongo_failure_as_empty',"$('history-status').textContent='История временно недоступна'","$('history-status').textContent='За выбранный период измерений нет'")]
        for name,old,new in mutations:
            if old not in source:raise ValueError('Stale selector: '+name)
            path=tmp/(name+'.js');path.write_text(source.replace(old,new,1))
            r=subprocess.run([sys.executable,'-m','scripts.check_stage9_dom','--directory',str(a.directory),'--script',str(path),'--output',str(tmp/(name+'.json'))],capture_output=True,text=True,timeout=80)
            output=r.stdout+r.stderr;killed=r.returncode==1 and 'AssertionError' in output and not any(s in output for s in ['SyntaxError','ModuleNotFoundError','ImportError'])
            results.append(dict(injected_defect=name,expected='DOM assertion failure',actual=output[-2500:],exit_code=r.returncode,behaviorally_detected=killed))
        report=dict(baseline_exit_code=0,baseline=json.loads((tmp/'baseline.json').read_text()),results=results,all_killed=all(r['behaviorally_detected'] for r in results))
        a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
        if not report['all_killed']:raise SystemExit(1)

if __name__=='__main__':main()
