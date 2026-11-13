"""Standalone figures of actual runs; censoring and missing values remain explicit."""
import argparse,json,statistics,math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser();p.add_argument('--reports',type=Path,default=Path('docs/reports/stage13'));a=p.parse_args();root=a.reports;allruns=json.loads((root/'performance-summary.json').read_text())['runs']
    runs=[r for r in allruns if r['requested_seconds']==300 and r['kind']=='policy_throughput'];figdir=root/'figures';figdir.mkdir(exist_ok=True)
    colors={'baseline':'tab:blue','optimized':'tab:green'}
    def save(fig,name):
        fig.tight_layout();fig.savefig(figdir/(name+'.png'),dpi=160);fig.savefig(figdir/(name+'.svg'));plt.close(fig)
    def groupbar(value,ylabel,name):
        fig,ax=plt.subplots(figsize=(10,5))
        for variant in colors:
            vals=[r for r in runs if r['variant']==variant]
            ax.scatter([r['devices'] for r in vals],[value(r) for r in vals],label=variant,color=colors[variant])
        ax.set(xlabel='Software devices (independent-run points)',ylabel=ylabel);ax.legend();save(fig,name)
    groupbar(lambda r:r['processed_per_second'],'Source observations processed/s while publishers continue','throughput_devices')
    fig,axes=plt.subplots(1,2,figsize=(13,4))
    for ax,variant in zip(axes,colors):
        r=next(v for v in runs if v['variant']==variant and v['devices']==25)
        for key,label in [('incoming_per_second','incoming'),('processed_per_second','processed')]:
            vals=[v for v in r['timeseries'] if v[key] is not None];ax.plot([v['elapsed'] for v in vals],[v[key] for v in vals],'.-',label=label)
        ax.set(title=variant+' /25 devices',xlabel='Elapsed seconds',ylabel='Observations/s between actual DB snapshots');ax.legend()
    save(fig,'incoming_processed')
    for key,name,ylabel in [('pending','backlog','Pending source journal identities'),('oldest_age','oldest_pending_age','Oldest pending source age, s')]:
        fig,axes=plt.subplots(1,2,figsize=(14,5))
        for r in [v for v in runs if v['devices']==25]:
            axes[0].plot([v['elapsed'] for v in r['timeseries']],[v[key] if v[key] is not None else math.nan for v in r['timeseries']],'.-',color=colors[r['variant']],alpha=.65,label=r['project'])
        for r in [v for v in allruns if v['requested_seconds']==900]:
            axes[1].plot([v['elapsed'] for v in r['timeseries']],[v[key] if v[key] is not None else math.nan for v in r['timeseries']],'.-',label=r['project'])
        for ax in axes:ax.set(xlabel='Elapsed seconds',ylabel=ylabel);ax.legend(fontsize=6)
        axes[0].set_title('Three independent25-device five-minute runs');axes[1].set_title('Measured15-minute optimized stability (no extrapolation)')
        save(fig,name)
    fig,ax=plt.subplots(figsize=(12,5));selected=[r for r in runs if r['devices']==25]
    for i,r in enumerate(selected):
        for key,marker in [('median','o'),('p95','s'),('p99','^')]:
            value=r['latency_inflight_seconds'].get(key)
            if isinstance(value,(int,float)):ax.scatter(i,value,marker=marker,color=colors[r['variant']],label=key if i==0 else None)
        ax.annotate('pending@stop '+str(r['inflight_pending']),(i,.97),xycoords=('data','axes fraction'),rotation=80,fontsize=7,ha='left',va='top')
    ax.set_xticks(range(len(selected)),[r['project'].split('policy-')[1] for r in selected],rotation=25,ha='right');ax.set(ylabel='Recorded event→Policy time, s',title='Conditional inflight latency; pending sources are censored, never zero');ax.legend();save(fig,'source_lag_quantiles')
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for variant in colors:
        rs=[r for r in runs if r['variant']==variant]
        axes[0].scatter([r['processed_per_second'] for r in rs],[r['policy_worker_cpu_percent']['mean'] for r in rs],label=variant,color=colors[variant])
        axes[1].scatter([r['processed_per_second'] for r in rs],[r['policy_worker_ram_mib']['mean'] for r in rs],label=variant,color=colors[variant])
    for ax in axes:ax.set_xlabel('Actual processing observations/s');ax.legend()
    axes[0].set_ylabel('Policy worker CPU%, sampled mean');axes[1].set_ylabel('Policy worker RAM MiB, sampled mean');save(fig,'cpu_throughput')
    ablation=json.loads((root/'ablation.json').read_text())['runs'];names=list(dict.fromkeys(r['case'] for r in ablation))
    fig,axes=plt.subplots(1,2,figsize=(14,5))
    for i,name in enumerate(names):
        rs=[r for r in ablation if r['case']==name];axes[0].scatter([i]*len(rs),[v['stats']['sql_seconds']*1e6/v['input'] for v in rs]);axes[1].scatter([i]*len(rs),[v['events_per_second'] for v in rs])
    for ax in axes:ax.set_xticks(range(len(names)),names,rotation=25,ha='right')
    axes[0].set_ylabel('Instrumented cursor wall, us/source');axes[1].set_ylabel('Controlled synthetic poll throughput, events/s');save(fig,'sql_time')
    fig,ax=plt.subplots(figsize=(11,5))
    for i,name in enumerate(names):
        rs=[r for r in ablation if r['case']==name];ax.scatter([i]*len(rs),[v['stats']['commits']/v['input'] for v in rs])
    ax.set_xticks(range(len(names)),names,rotation=25,ha='right');ax.set_ylabel('Application Policy processing transactions/source (startup/heartbeat excluded)');save(fig,'transactions_event')
    fig,ax=plt.subplots(figsize=(11,5))
    for variant in colors:
        rs=[r for r in runs if r['variant']==variant];ax.scatter([r['devices'] for r in rs],[r['drain_seconds'] for r in rs],color=colors[variant],label=variant)
        for r in rs:
            if r['final_pending']:ax.annotate('censored; remaining '+str(r['final_pending']),(r['devices'],r['drain_seconds']),fontsize=6,rotation=10)
    ax.set(xlabel='Devices',ylabel='Post-publisher-stop observed drain duration, s',title='Incomplete baseline drains are right-censored, not completed recovery');ax.legend();save(fig,'drain_recovery')
    golden=json.loads((root/'golden-release.json').read_text())['traces'];fig,ax=plt.subplots(figsize=(12,4));ax.scatter(range(len(golden)),[0 if t['equal'] else 1 for t in golden]);ax.set_xticks(range(len(golden)),[t['trace'] for t in golden],rotation=45,ha='right');ax.set(ylim=(-.1,1.1),ylabel='Golden mismatch (actual comparison)',title='Full expected/actual traces retained; state times and source identities compared');save(fig,'decision_correctness')
    fig,axes=plt.subplots(1,2,figsize=(12,4));sec=sum(r['incoming_observations'] for r in runs);axes[0].bar(['security observations','ML worker disabled'],[sec,0]);axes[0].set_title('Measured real MQTT load; ML zero is observed disabled mode')
    full=next(t for t in golden if t['trace']=='full-queue-110-security-ml');trace=full['optimized']['processing_trace'];axes[1].bar(['security','research ML'],[sum(t['signal']['source']!='ml' for t in trace),sum(t['signal']['source']=='ml' for t in trace)]);axes[1].set_title('Separate real-PG fixture fairness; not live model inference');save(fig,'ml_security_distribution')
    fig,axes=plt.subplots(1,2,figsize=(13,4))
    for ax,variant in zip(axes,colors):
        r=next(v for v in runs if v['variant']==variant and v['devices']==25)
        for key,label in [('evidence_age','last actually processed source age'),('heartbeat_age','heartbeat age')]:ax.plot([v['elapsed'] for v in r['timeseries']],[v[key] if v[key] is not None else math.nan for v in r['timeseries']],'.-',label=label)
        ax.axhline(60,color='grey',linestyle='--',label='default telemetry freshness60s');ax.set(title=variant,xlabel='Elapsed seconds',ylabel='Age seconds');ax.legend(fontsize=7)
    save(fig,'freshness_heartbeat')
    admission=[r for r in allruns if r['admission']];fig,ax=plt.subplots(figsize=(10,4))
    for i,variant in enumerate(colors):
        vals=[r['admission']['transaction_wall_seconds']['median']*1000 for r in admission if r['variant']==variant];ax.scatter([i]*len(vals),vals,color=colors[variant])
    ax.set_xticks([0,1],list(colors));ax.set(ylabel='Successful receiver transaction wall median, ms',title='Two independent short matched25-device runs; interrupted repeats excluded; checkout/SQL/commit included');save(fig,'admission_transaction_wall')
    print('13 actual-data figure families exported; no confidence intervals or missing-as-zero')
if __name__=='__main__':main()
