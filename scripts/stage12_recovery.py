"""Reuse verified real-service fault harness, scoped to independent Stage12 lab."""
from scripts.crypto_research_lab import Lab
from scripts import check_kuz_reliability
check_kuz_reliability.Lab=Lab
if __name__=='__main__':check_kuz_reliability.main()
