"""Read frozen results only. No fitting/prediction/threshold selection; train-val feature audit."""
import argparse,json,hashlib,platform
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.classifier.research.schema import FEATURES,packet_frame


def main():
 p=argparse.ArgumentParser();p.add_argument('--reports',type=Path,default=Path('docs/reports/stage14'));p.add_argument('--dataset',type=Path,default=Path('.local-runtime/stage14/lightcrypto-lab-v1'));a=p.parse_args();r=a.reports
 result=json.loads((r/'rf-if-results.json').read_text());freeze=json.loads((r/'train-freeze.json').read_text());config=json.loads((r/'training-config.json').read_text());plan=json.loads(Path('.local-runtime/stage14/study/plan.json').read_text());frame=pd.read_csv(a.dataset/'dataset.csv');obs=pd.read_csv(a.dataset/'observations.csv',keep_default_na=False)
 indices=plan['split']['indices'];audit=frame.iloc[indices[0]+indices[1]].copy();assert not set(audit.packet_id)&set(frame.iloc[indices[2]].packet_id)
 distributions={}
 for name,sub in audit.groupby('attack_type'):distributions[name]={field:{k:float(v) for k,v in sub[field].describe(percentiles=[.25,.5,.75]).items()} for field in FEATURES}
 hashes=pd.util.hash_pandas_object(packet_frame(audit),index=False);groups=audit.assign(_fp=hashes.to_numpy()).groupby('_fp');collisions=dict(unique_vectors=int(hashes.nunique()),rows=len(audit),repeated_value_rows=int(hashes.duplicated(keep=False).sum()),conflicting_label_vectors=int(groups.label.nunique().gt(1).sum()),meaning='Equal feature values do not prove duplicate physical packets')
 conn=obs.groupby('session_id').ground_truth.agg(lambda x:set(x)-{'unknown'});counts=dict(normal_connections=int(sum(v=={'normal'} for v in conn)),controlled_violation_connections=int(sum(v=={'controlled_violation'} for v in conn)),connections_without_known_rows=int(sum(not v for v in conn)),total_tcp_sessions=len(conn))
 leakage=dict(performed_at=datetime.now(timezone.utc).isoformat(),scope='Descriptive post-evaluation train/validation only; not used to tune frozen models',holdout_features_or_labels_used_for_this_audit=False,model_choices_changed=False,predictors=FEATURES,excluded_metadata=[v for v in frame.columns if v not in FEATURES],feature_distributions_by_class=distributions,feature_value_collisions=collisions,confounders=['single physical host/OS/stack','same producer/collector implementation','six heldout blocks only','scenario density and TLS connection-duration effects','paired conditions within blocks','conservative transductive crossing-fingerprint isolation changes prevalence','only one declared random seed/model run','bad_credentials validation positive support absent'],external_domain_validation='not_performed',shortcut_absence_proven=False)
 (r/'leakage-audit.json').write_text(json.dumps(leakage,indent=2));source_receipts=[json.loads(p.read_text()) for p in Path('.local-runtime/stage14/primary-captures').glob('*/acquisition.json')]
 independent=dict(acquisition_blocks=len({x['group'] for x in source_receipts}),broker_realms=len({x['project'] for x in source_receipts}),physical_hosts=len({x['host_identity_sha256'] for x in source_receipts}),captures=len(source_receipts),pcap_digests_unique=len({x['pcap_sha256'] for x in source_receipts}),partitions={name:len({x['group'] for x in source_receipts if x['partition']==name}) for name in ['train','validation','test']},independence_scope='Preregistered repeated acquisition blocks within one fixed software domain; no universal IID/hardware proof',connections=counts,retained_split_summary=plan['split']['summary'],fingerprint_purged_rows=plan['split']['duplicate_purged_rows'])
 (r/'independence-analysis.json').write_text(json.dumps(independent,indent=2))
 specs={v['candidate_id']:v for v in config['candidates']};table=[]
 for row in result['results']:
  candidate=next(v for v in freeze['models'] if v['model_id']==row['model_id']);m=row['metrics'];s=m['stage14']['session'];spec=specs[candidate['candidate_id']]
  table.append(dict(candidate=candidate['candidate_id'],algorithm=candidate['algorithm'],ablation=candidate['ablation'],features=','.join(spec['features']),packet_threshold=row['threshold'],validation_f1=candidate['validation']['f1'],validation_fpr=candidate['validation']['fpr'],test_precision=m['precision'],test_recall=m['recall'],test_f1=m['f1'],test_fpr=m['fpr'],test_pr_auc=m['pr_auc'],test_roc_auc=m['roc_auc'],session_method=candidate['session_calibration']['selected']['method'],session_threshold=candidate['session_calibration']['selected']['point']['threshold'],session_precision=s['precision'],session_recall=s['recall'],session_f1=s['f1'],session_fpr=s['fpr']))
 pd.DataFrame(table).to_csv(r/'model-comparison.csv',index=False);(r/'model-comparison.json').write_text(json.dumps(dict(models=table,selection_source='Original validation-only winners; all23 frozen candidates reported',winners=freeze['winners'],exit_code=0),indent=2))
 figures=r/'figures';figures.mkdir(exist_ok=True)
 def save(fig,name):fig.tight_layout();fig.savefig(figures/(name+'.png'),dpi=150);fig.savefig(figures/(name+'.svg'));plt.close(fig)
 fig,ax=plt.subplots(figsize=(9,4));count=obs.ground_truth.value_counts();ax.bar(count.index,count.values);ax.set(ylabel='Actual TCP observations',title='Primary60 captures: connection/window labels, not malicious packets');save(fig,'labels')
 fig,axes=plt.subplots(1,2,figsize=(12,4));axes[0].bar(['Normal','ControlledViolation','Unknown'],[counts['normal_connections'],counts['controlled_violation_connections'],counts['connections_without_known_rows']]);axes[0].set_ylabel('TCP sessions supporting known rows / no known rows');axes[1].bar(['train','validation','test'],[18,6,6]);axes[1].set_ylabel('Acquisition blocks (paired captures not independent)');save(fig,'independent_units')
 base=[v for v in table if not v['ablation']];fig,axes=plt.subplots(1,3,figsize=(16,5));names=[v['candidate'] for v in base]
 for ax,key,title in zip(axes,['test_recall','test_fpr','test_f1'],['Packet recall','Packet FPR','Packet F1']):ax.bar(names,[v[key] for v in base]);ax.tick_params(axis='x',rotation=70);ax.set_ylim(0,1);ax.set_title(title+' / frozen holdout known subset')
 save(fig,'base_metrics')
 fig,axes=plt.subplots(1,2,figsize=(15,5))
 for ax,algorithm in zip(axes,['rf','if']):
  rows=[v for v in table if v['algorithm']==algorithm and v['ablation']];ax.bar(np.arange(len(rows))-.18,[v['validation_f1'] for v in rows],width=.36,label='validation');ax.bar(np.arange(len(rows))+.18,[v['test_f1'] for v in rows],width=.36,label='one frozen test');ax.set_xticks(range(len(rows)),[v['candidate'].split('ablation_')[1] for v in rows],rotation=55,ha='right');ax.set(title=algorithm+' preregistered ablations',ylabel='F1 (no post-test selection)',ylim=(0,1));ax.legend()
 save(fig,'ablations')
 for task in ['rf_binary','if','rf_session','if_session']:
  row=next(v for v in result['results'] if v['model_id']==freeze['winners'][task]);m=row['metrics'];session=task.endswith('session');matrix=m['stage14']['session']['confusion_matrix'] if session else m['confusion_matrix'];fig,ax=plt.subplots(figsize=(5,4));ax.imshow(matrix,cmap='Blues')
  for i in range(2):
   for j in range(2):ax.text(j,i,str(matrix[i][j]),ha='center',va='center')
  ax.set(xticks=[0,1],yticks=[0,1],xticklabels=['Normal','ControlledViolation'],yticklabels=['Normal','ControlledViolation'],xlabel='Predicted',ylabel='Corroborated target',title=task+' / validation-selected model');save(fig,'confusion_'+task)
 fig,axes=plt.subplots(1,5,figsize=(19,4))
 for ax,field in zip(axes,FEATURES):
  for label,sub in audit.groupby('attack_type'):ax.hist(np.log1p(sub[field].to_numpy()),bins=35,alpha=.5,density=True,label=label)
  ax.set(title=field,xlabel='log1p(value), train/validation only');ax.legend(fontsize=6)
 save(fig,'feature_distributions_train_validation')
 print('Frozen-result tables/9 figure families and train-val-only descriptive audit; no model execution; exit0')
if __name__=='__main__':main()
