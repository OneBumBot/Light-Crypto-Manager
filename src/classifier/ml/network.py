"""Offline IDS with train-only transforms and explicit future-collector interface."""
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from .schema import network_frame, NETWORK_NUMERIC, NETWORK_CATEGORICAL, NETWORK_VERSION


class NetworkSchema(BaseEstimator,TransformerMixin):
    def __init__(self,version=NETWORK_VERSION): self.version=version
    def fit(self,X,y=None):
        network_frame(X,self.version)
        return self
    def transform(self,X): return network_frame(X,self.version)


def build_network(algorithm,seed=42,trees=100):
    numeric=Pipeline([('impute',SimpleImputer(strategy='median',keep_empty_features=True)),
                      ('scale',StandardScaler())])
    categorical=Pipeline([('impute',SimpleImputer(strategy='constant',fill_value='__MISSING__',keep_empty_features=True)),
        ('encode',OneHotEncoder(handle_unknown='ignore',max_categories=64,sparse_output=False))])
    preprocess=ColumnTransformer([('numeric',numeric,NETWORK_NUMERIC),
                                 ('categorical',categorical,NETWORK_CATEGORICAL)],remainder='drop')
    if algorithm in ('rf_binary','rf_multiclass'):
        estimator=RandomForestClassifier(n_estimators=trees,random_state=seed,n_jobs=1,class_weight='balanced')
    elif algorithm=='isolation_forest':
        estimator=IsolationForest(n_estimators=trees,random_state=seed,n_jobs=1,contamination='auto')
    else: raise ValueError('Unsupported IDS algorithm')
    return Pipeline([('schema',NetworkSchema()),('prepare',preprocess),('model',estimator)])


def risk_scores(pipeline,X,algorithm):
    if algorithm=='isolation_forest': return -pipeline.score_samples(X)
    classes=list(pipeline.classes_)
    normal=0 if algorithm=='rf_binary' else 'Normal'
    if normal not in classes: raise ValueError('Normal class absent from fitted classifier')
    return 1-pipeline.predict_proba(X)[:,classes.index(normal)]
