"""Local import -> frozen split -> train/validation -> once-only test. Offline only."""
import argparse
import json
import os
from pathlib import Path
from .datasets import import_csv
from .experiment import plan,train,final_test


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['import','plan','train','test','external'])
    for key in ['data','manifest','config','output','plan','models','experiment']:parser.add_argument('--'+key)
    args=parser.parse_args()
    try:
        def need(name):
            value=getattr(args,name)
            if not value:raise ValueError('--'+name+' is required')
            return value
        if args.command=='import':result=import_csv(json.loads(Path(need('config')).read_text()),need('output'))
        elif args.command=='plan':result=plan(need('data'),need('manifest'),json.loads(Path(need('config')).read_text()),need('output'))
        elif args.command=='train':result=train(need('data'),need('manifest'),need('plan'),need('models'),need('experiment'))
        elif args.command=='external':
            from .external import evaluate_external
            result=evaluate_external(need('data'),need('manifest'),need('models'),need('experiment'),need('output'))
        else:result=final_test(need('data'),need('manifest'),need('plan'),need('models'),need('experiment'))
        print(json.dumps({'status':'completed','command':args.command,'synthetic':result.get('synthetic'),
            'scope':result.get('scope'),'rows':result.get('rows'),'trusted_detector':False}))
    except (ValueError,KeyError,FileNotFoundError,FileExistsError) as e:
        parser.exit(2,'Research run rejected: '+str(e)+'\n')

if __name__=='__main__':main()
