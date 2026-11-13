"""Stage15-only bounded extension of existing TLS/AEAD generator; no old limits changed."""
import argparse,json
from pathlib import Path
from src.research_stand.config import Experiment
from src.research_stand.driver import run
class Workload(Experiment):
 def validate(self):
  # Reuse every established scenario/type/duration/rate check on a <=24 proxy,
  # then separately enforce Stage15 concurrent identities and aggregate resource bound.
  Experiment(**{**self.__dict__,'clients':min(self.clients,24)}).validate()
  if type(self.clients) is not int or not 2<=self.clients<=50 or self.clients/self.interval>120:raise ValueError('Stage15 bounded50 clients/120messages per second')
  return self
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args();run(Workload(**json.loads(Path(a.config).read_text())),'/research')
