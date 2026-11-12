"""Export measured data as standalone figures. No synthetic samples or CIs."""
import argparse,json,statistics,csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser();p.add_argument('--reports',type=Path,default=Path('docs/reports/stage12'));a=p.parse_args();root=a.reports
    micro=json.loads((root/'comparative-final.json').read_text())['runs'];figdir=root/'figures';figdir.mkdir(exist_ok=True)
    ids=list(dict.fromkeys(r['implementation'] for r in micro));colors=dict(zip(ids,plt.cm.tab10.colors));labels={i:i.replace('kuz-','Kuz/').replace('ascon-','Ascon/').replace('aes-','AES/') for i in ids}
    labels['kuz-go-one-shot']='Kuz/original Stage11 one-shot'
    labels['kuz-go-worker']='Kuz/bounded Go worker'
    def save(fig,name):fig.tight_layout();fig.savefig(figdir/(name+'.png'),dpi=160);fig.savefig(figdir/(name+'.svg'));plt.close(fig)
    for key,name in [('encrypt_ns','encryption_payload'),('decrypt_ns','decryption_payload')]:
        fig,axes=plt.subplots(1,2,figsize=(13,5))
        for ax,mode in zip(axes,['fixed','telemetry']):
            for impl in ids:
                rows=[r for r in micro if r['implementation']==impl and r['aad_mode']==mode]
                ax.scatter([r['payload_bytes'] for r in rows],[r[key]['median']/1000 for r in rows],label=labels[impl],color=colors[impl],s=17)
            ax.set(xlabel='Payload bytes',ylabel='Run median latency, us',title=mode+' AAD; five measured runs',yscale='log');ax.legend(fontsize=7)
        save(fig,name)
    rows=[r for r in micro if r['payload_bytes']==83 and r['aad_mode']=='fixed']
    def groups(data,value,name,ylabel):
        fig,ax=plt.subplots(figsize=(11,5))
        for x,impl in enumerate(ids):
            v=[value(r) for r in data if r['implementation']==impl]
            if v:ax.scatter([x]*len(v),v,color=colors[impl]);ax.bar(x,statistics.median(v),alpha=.2,color=colors[impl])
        ax.set_xticks(range(len(ids)),[labels[i] for i in ids],rotation=18,ha='right');ax.set_ylabel(ylabel);ax.set_title('83B / fixed AAD; independent-run points, median bars');save(fig,name)
    groups(rows,lambda r:r['pairs_per_second'],'throughput','Authenticated encrypt/decrypt pairs per second')
    cpu=json.loads((root/'cpu-final.json').read_text())['runs'] if (root/'cpu-final.json').exists() else rows
    groups(cpu,lambda r:1e6*(r['python_cpu_seconds']+r['child_cpu_seconds'])/r['iterations'],'cpu','Python + child CPU, us per authenticated pair')
    fig,ax=plt.subplots(figsize=(11,5))
    for x,impl in enumerate(ids):
        r=[v for v in rows if v['implementation']==impl];ax.scatter([x]*len(r),[v['python_rss_kib']/1024 for v in r],label='Python RSS' if x==0 else None,color='tab:blue')
        children=[v['child_rss_kib']/1024 for v in r if v['child_rss_kib'] is not None]
        if children:ax.scatter([x]*len(children),children,label='Child RSS (separate peak)' if impl=='kuz-go-one-shot' else None,color='tab:orange')
    ax.set_xticks(range(len(ids)),[labels[i] for i in ids],rotation=18,ha='right');ax.set_ylabel('MiB; peaks are not summed');ax.legend();save(fig,'rss')
    groups(rows,lambda r:r['ciphertext_bytes']-r['payload_bytes'],'ciphertext_expansion','Measured ciphertext expansion, bytes')
    native=json.loads((root/'native-instrumentation.json').read_text());fig,ax=plt.subplots(figsize=(10,5))
    for x,key in enumerate(['startup_original_ns','startup_optimized_ns','echo_roundtrip_ns','native_encrypt_ns','native_decrypt_ns','key_setup_ns']):
        values=[statistics.median(r[key])/1000 for r in native['runs']];ax.scatter([x]*len(values),values);ax.bar(x,statistics.median(values),alpha=.2)
    ax.set_xticks(range(6),['original startup+reject','optimized startup+reject','echo IPC only','native encrypt','native decrypt','CT key setup'],rotation=18,ha='right');ax.set(ylabel='us, log scale',yscale='log',title='Separate measured boundaries; no startup subtraction');save(fig,'startup_ipc_native')
    system=json.loads((root/'system.json').read_text());fig,axes=plt.subplots(1,2,figsize=(15,5));names=[]
    for x,w in enumerate(system['windows']):
        names.append(w['profile'].replace('-v1','')+'/'+w['backend'])
        rows=[r for r in w['reconciliation']['rows'] if r['device']=='alpha']
        axes[0].scatter([x]*len(rows),[r['sensor_to_receiver_created_ms'] for r in rows],s=13)
        delivered=[r for r in rows if r['pg_created_to_delivery_ms'] is not None]
        # Algebra of two measured same-clock intervals sharing the created_at endpoint.
        axes[1].scatter([x]*len(delivered),[r['sensor_to_receiver_created_ms']+r['pg_created_to_delivery_ms'] for r in delivered],s=13)
    for ax in axes:ax.set_xticks(range(len(names)),names,rotation=25,ha='right')
    axes[0].set_ylabel('Sensor to receiver-created, ms; not isolated commit latency')
    axes[1].set_ylabel('Sensor to Outbox delivered_at after Mongo ACK, ms')
    save(fig,'mqtt_latency')
    fig,ax=plt.subplots(figsize=(10,4));ts=system['transitions'];ax.bar(range(len(ts)),[r['observed_effective_seconds'] for r in ts]);ax.set_xticks(range(len(ts)),[r['target'].replace('-v1','') for r in ts],rotation=20,ha='right');ax.set_ylabel('HTTP request to observed EFFECTIVE_CONFIRMED, s');save(fig,'switch_latency')
    final=json.loads((root/'final.json').read_text());fig,axes=plt.subplots(1,2,figsize=(10,4));u=final['usage'];axes[0].bar([r['device_id'] for r in u],[r['reserved_invocations'] for r in u]);axes[0].set_ylabel('Actual reserved MGM invocations (burned allowance)');axes[1].axis('off');axes[1].text(.05,.5,'Magma rotation: not implemented\nCost: not_measured\nNo live activation\nNo zero-cost bar fabricated');save(fig,'usage_rotation')
    with (root/'run-summary.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['repeat','implementation','profile','payload_bytes','aad_mode','median_encrypt_ns','median_decrypt_ns','pairs_per_second','source_dataset'])
        for r in micro:writer.writerow([r['repeat'],r['implementation'],r['profile'],r['payload_bytes'],r['aad_mode'],r['encrypt_ns']['median'],r['decrypt_ns']['median'],r['pairs_per_second'],r.get('source_dataset','not_recorded')])
    print('10 measured figure families exported; Magma absent from live plots')

if __name__=='__main__':main()
