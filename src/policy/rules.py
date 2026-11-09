"""Declarative bounded policy settings. No expression evaluator."""
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Rules:
    window_seconds: int = 60
    max_age_seconds: int = 120
    future_skew_seconds: int = 5
    cooldown_seconds: int = 30
    recovery_seconds: int = 300
    recovery_observations: int = 6
    watch_observations: int = 2
    alert_observations: int = 3
    min_decision_seconds: int = 1
    telemetry_fresh_seconds: int = 60
    ml_fresh_seconds: int = 120
    minimum_profile: str = 'ascon-aead128-v1'
    elevated_profile: str = 'ascon-aead128-v1'
    strategy: str = 'adaptive_hysteresis'

    def validate(self):
        for k,v in asdict(self).items():
            if k in {'minimum_profile','elevated_profile','strategy'}:continue
            if type(v) is not int or not 0 <= v <= 86400:raise ValueError('Invalid rule bound: '+k)
        if self.window_seconds<1 or self.max_age_seconds<1 or self.telemetry_fresh_seconds<1 or self.ml_fresh_seconds<1:
            raise ValueError('Positive freshness windows required')
        if not 1<=self.watch_observations<=self.alert_observations<=128 or not 2<=self.recovery_observations<=128:
            raise ValueError('Invalid confirmation counts')
        if self.recovery_seconds<self.cooldown_seconds:raise ValueError('Recovery must exceed cooldown')
        if self.strategy not in {'fixed','adaptive','adaptive_research','adaptive_hysteresis'}:
            raise ValueError('Unsupported strategy')
        for p in [self.minimum_profile,self.elevated_profile]:
            if type(p) is not str or len(p)>64:raise ValueError('Invalid profile ID')
        return self

    def payload(self):return asdict(self.validate())

    @classmethod
    def parse(cls,value):
        if type(value) is not dict:raise ValueError('Rules must be an object')
        try:return cls(**value).validate()
        except TypeError as e:raise ValueError('Unknown rule setting') from e
