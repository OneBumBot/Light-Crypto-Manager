"""Figures from actual Stage10 artifacts only; no synthetic interpolation."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser();p.add_argument('--reports',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    rows=sorted([json.loads(p.read_text()) for p in a.reports.glob('load-*/result.json')],key=lambda r:r['devices'])
    def chart(name,x,y,xlabel,ylabel):
        fig,ax=plt.subplots(figsize=(7,4));ax.scatter(x,y);ax.set(xlabel=xlabel,ylabel=ylabel,title=name);ax.grid(alpha=.25);fig.tight_layout();fig.savefig(a.output/(name+'.png'),dpi=160);plt.close(fig)
    for title,key,label in [('throughput-vs-devices','throughput','committed window events / second'),('cpu-vs-devices','cpu_percent','CPU % of one core'),('ram-vs-devices','ram_mib','Docker working memory MiB'),('latency-vs-devices','measured_to_delivery_finish_seconds','median measured→delivery finish seconds')]:
        ys=[r[key]['median'] if key!='throughput' else r[key] for r in rows];chart(title,[r['devices'] for r in rows],ys,'Provisioned software devices',label)
    fig,ax=plt.subplots(figsize=(7,4))
    for run in rows:
        samples=json.loads((a.reports/('load-'+str(run['devices']))/'samples.json').read_text());ax.plot([s['elapsed'] for s in samples],[sum(v for k,v in s['sql']['outbox'].items() if k!='delivered') for s in samples],label=str(run['devices'])+' devices')
    ax.set(xlabel='Elapsed seconds',ylabel='Outbox not delivered',title='Observed backlog (sampled)');ax.legend();fig.tight_layout();fig.savefig(a.output/'outbox-backlog.png',dpi=160);plt.close(fig)
    switches=[];recoveries=[]
    for file in a.reports.glob('reliability-*.json'):
        r=json.loads(file.read_text());switches.extend((r['devices'],s['observed_effective_seconds']) for s in r['switches']);recoveries.extend((s['service'],s['post_start_recovery_seconds']) for s in r['faults'])
    if switches:chart('switch-vs-load',[s[0] for s in switches],[s[1] for s in switches],'Software devices','HTTP request→observed verified effective seconds')
    if recoveries:chart('recovery-by-fault',[s[0] for s in recoveries],[s[1] for s in recoveries],'Fault scenario','After service start→observed drain seconds')
    micro=json.loads((a.reports/'crypto-microbenchmark.json').read_text())
    fig,axs=plt.subplots(1,2,figsize=(10,4))
    for ax,op in zip(axs,['encrypt_ns','decrypt_ns']):
        for profile in ['ascon-aead128-v1','aes-128-gcm-v1']:
            runs=[r for r in micro['runs'] if r['profile']==profile];ax.scatter([r['size'] for r in runs],[r['summary'][op]['median']/1000 for r in runs],label=profile)
        ax.set(xlabel='Plaintext bytes',ylabel='Median microseconds',yscale='log',title=op);ax.legend(fontsize=7);ax.grid(alpha=.25)
    fig.tight_layout();fig.savefig(a.output/'crypto-implementations.png',dpi=160);plt.close(fig)
    print('Figures contain actual observed runs only; no capacity extrapolation')

if __name__=='__main__':main()
