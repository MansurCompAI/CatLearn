""" Script to test descriptors for the ML model. Takes a database of candidates
    from with target values set in atoms.info['key_value_pairs'][key] and
    returns the correlation of descriptors with target values.
"""
from __future__ import print_function
from __future__ import absolute_import

import numpy as np

from ase.ga.data import DataConnection
from atoml.data_setup import get_unique, get_train
from atoml.fingerprint_setup import return_fpv, normalize
from atoml.feature_select import (lasso, sure_independence_screening,
                                  iterative_screening,
                                  robust_rank_correlation_screening, pca)
from atoml.particle_fingerprint import ParticleFingerprintGenerator
from atoml.standard_fingerprint import StandardFingerprintGenerator
from atoml.predict import GaussianProcess

# Connect database generated by a GA search.
db = DataConnection('gadb.db')

# Get all relaxed candidates from the db file.
print('Getting candidates from the database')
all_cand = db.get_all_relaxed_candidates(use_extinct=False)

# Setup the test and training datasets.
testset = get_unique(candidates=all_cand, testsize=50, key='raw_score')
trainset = get_train(candidates=all_cand, trainsize=50,
                     taken_cand=testset['taken'], key='raw_score')

# Get the list of fingerprint vectors and normalize them.
print('Getting the fingerprint vectors')
fpv = ParticleFingerprintGenerator(get_nl=False, max_bonds=13)
std = StandardFingerprintGenerator()
test_fp = return_fpv(testset['candidates'], [fpv.nearestneighbour_fpv,
                                             fpv.bond_count_fpv,
                                             fpv.distribution_fpv,
                                             fpv.rdf_fpv,
                                             std.mass_fpv,
                                             std.eigenspectrum_fpv,
                                             std.distance_fpv])
train_fp = return_fpv(trainset['candidates'], [fpv.nearestneighbour_fpv,
                                               fpv.bond_count_fpv,
                                               fpv.distribution_fpv,
                                               fpv.rdf_fpv,
                                               std.mass_fpv,
                                               std.eigenspectrum_fpv,
                                               std.distance_fpv])


def do_pred(ptrain_fp, ptest_fp):
    nfp = normalize(train=ptrain_fp, test=ptest_fp)
    print('Feature length:', len(nfp['train'][0]))

    # Do the predictions.
    pred = gp.get_predictions(train_fp=nfp['train'],
                              test_fp=nfp['test'],
                              train_target=trainset['target'],
                              test_target=testset['target'],
                              get_validation_error=True,
                              get_training_error=True,
                              optimize_hyperparameters=False)

    # Print the error associated with the predictions.
    print('Training error:', pred['training_rmse']['average'])
    print('Model error:', pred['validation_rmse']['average'])


# Set up the prediction routine.
kdict = {'k1': {'type': 'gaussian', 'width': 0.5}}
gp = GaussianProcess(kernel_dict=kdict, regularization=0.001)

# Get base predictions.
print('Base Predictions')
do_pred(ptrain_fp=train_fp, ptest_fp=test_fp)

print('PCA Predictions')
for i in range(min(len(test_fp), len(test_fp[0])) - 1):
    pca_r = pca(components=i + 1, train_fpv=train_fp, test_fpv=test_fp)
    do_pred(ptrain_fp=pca_r['train_fpv'], ptest_fp=pca_r['test_fpv'])

print('LASSO Predictions')
ls = lasso(size=40, steps=100, target=trainset['target'],
           train_matrix=train_fp, test_matrix=test_fp,
           test_target=testset['target'])
print('linear model error:', ls['linear_error'])
do_pred(ptrain_fp=ls['train_matrix'], ptest_fp=ls['test_matrix'])

# Get correlation for descriptors from SIS.
print('Getting descriptor correlation')
sis = sure_independence_screening(target=trainset['target'],
                                  train_fpv=train_fp, size=40)
print('sis features (pearson):', sis['accepted'])
print('sis correlation (pearson):', sis['correlation'])
sis_test_fp = np.delete(test_fp, sis['rejected'], 1)
sis_train_fp = np.delete(train_fp, sis['rejected'], 1)
do_pred(ptrain_fp=sis_train_fp, ptest_fp=sis_test_fp)

rrcs = robust_rank_correlation_screening(target=trainset['target'],
                                         train_fpv=train_fp, size=40)
print('rrcs features (kendall):', rrcs['accepted'])
print('rrcs correlation (kendall):', rrcs['correlation'])
rrcs_test_fp = np.delete(test_fp, rrcs['rejected'], 1)
rrcs_train_fp = np.delete(train_fp, rrcs['rejected'], 1)
do_pred(ptrain_fp=rrcs_train_fp, ptest_fp=rrcs_test_fp)

rrcs = robust_rank_correlation_screening(target=trainset['target'],
                                         train_fpv=train_fp, size=40,
                                         corr='spearman')
print('rrcs features (spearman):', rrcs['accepted'])
print('rrcs correlation (spearman):', rrcs['correlation'])
rrcs_test_fp = np.delete(test_fp, rrcs['rejected'], 1)
rrcs_train_fp = np.delete(train_fp, rrcs['rejected'], 1)
do_pred(ptrain_fp=rrcs_train_fp, ptest_fp=rrcs_test_fp)

it_sis = iterative_screening(target=trainset['target'], train_fpv=train_fp,
                             test_fpv=test_fp, size=40, step=4, method='sis')
print('iterative_sis features:', it_sis['accepted'])
print('iterative_sis correlation:', it_sis['correlation'])
do_pred(ptrain_fp=it_sis['train_fpv'], ptest_fp=it_sis['test_fpv'])

it_rrcs = iterative_screening(target=trainset['target'], train_fpv=train_fp,
                              test_fpv=test_fp, size=40, step=4, method='rrcs',
                              corr='kendall')
print('iterative_rrcs features (kendall):', it_rrcs['accepted'])
print('iterative_rrcs correlation (kendall):', it_rrcs['correlation'])
do_pred(ptrain_fp=it_rrcs['train_fpv'], ptest_fp=it_rrcs['test_fpv'])

it_rrcs = iterative_screening(target=trainset['target'], train_fpv=train_fp,
                              test_fpv=test_fp, size=40, step=4, method='rrcs',
                              corr='spearman')
print('iterative_rrcs features (spearman):', it_rrcs['accepted'])
print('iterative_rrcs correlation (spearman):', it_rrcs['correlation'])
do_pred(ptrain_fp=it_rrcs['train_fpv'], ptest_fp=it_rrcs['test_fpv'])
