""" Functions to setup fingerprint vectors. """
import numpy as np
from collections import defaultdict

import ase.db
from .data_setup import target_standardize


def db_sel2fp(calctype, fname, selection, moldb=None, bulkdb=None,
              slabref=None):
    """ Function to return an array of fingerprints from ase.db files and
        selection.

        Inputs:
            calctype: str
            fname: str
            selection: list
            moldb: str
            bulkdb: str
            DFT_parameters: dict
    """
    keys = {}
    c = ase.db.connect(fname)
    s = c.select(selection)
    for d in s:
        keys.update(d.key_value_pairs)
    k = list(keys)
    print(k)
    fpv = []
    if calctype == 'adsorption':
        assert moldb is not None
        from adsorbate_fingerprint import AdsorbateFingerprintGenerator
        if 'enrgy' in k:
            if slabref is None:
                slabs = fname
            fpv_gen = AdsorbateFingerprintGenerator(moldb=moldb, bulkdb=bulkdb,
                                                    slabs=slabs)
            cand = fpv_gen.db2adds_info(fname=fname, selection=selection)
            fpv += [fpv_gen.get_Ef]
        else:
            fpv_gen = AdsorbateFingerprintGenerator(moldb=moldb, bulkdb=bulkdb)
            cand = fpv_gen.db2adds_info(fname=fname, selection=selection)
        fpv += [fpv_gen.Z_add]
        try:
            from mendeleev import element
            fpv += [fpv_gen.primary_addatom,
                    fpv_gen.primary_adds_nn,
                    fpv_gen.adds_sum,
                    fpv_gen.primary_surfatom]
            if bulkdb is not None:
                fpv += [fpv_gen.primary_surf_nn]
        except ImportError:
            print('Mendeleev not imported. Certain fingerprints excluded.')
        if bulkdb is not None:
            fpv += [fpv_gen.elemental_dft_properties]
        cfpv = return_fpv(cand, fpv)
    elif calctype == 'nanoparticle':
        from particle_fingerprint import ParticleFingerprintGenerator
        fpv_gen = ParticleFingerprintGenerator()
        fpv += [fpv_gen.atom_numbers,
                fpv_gen.bond_count_fpv,
                fpv_gen.connections_fpv,
                fpv_gen.distribution_fpv,
                fpv_gen.nearestneighbour_fpv,
                fpv_gen.rdf_fpv]
        cfpv = return_fpv(cand, fpv)
    fpv_labels = get_combined_descriptors(fpv)
    return cfpv, fpv_labels


def get_combined_descriptors(fpv_list):
    """ Function to sequentially combine feature label vectors and return them
        for a list of atoms objects. Analogous to get_combined_fpv

        Input:  atoms object
                functions that return fingerprints

        Output:  list
    """
    # Check that there are at least two fingerprint descriptors to combine.
    msg = "This functions combines various fingerprint"
    msg += " vectors, there must be at least two to combine"
    assert len(fpv_list) >= 2, msg
    labels = fpv_list[::-1]
    L_F = []
    for j in range(len(labels)):
        L_F.append(labels[j]())
    return np.hstack(L_F)


def get_keyvaluepair(c=[], fpv_name='None'):
    if len(c) == 0:
        return ['kvp_'+fpv_name]
    else:
        out = []
        for atoms in c:
            field_value = float(atoms['key_value_pairs'][fpv_name])
            out.append(field_value)
        return out


def return_fpv(candidates, fpv_name, use_prior=True):
    """ Function to sequentially combine fingerprint vectors and return them
        for a list of atoms objects.
    """
    #Put fpv_name in a list, if it is not already.
    if not isinstance(fpv_name, list):
        fpv_name = [fpv_name]
    # Check to see if we are dealing with a list of candidates or a single
    # atoms object.
    if type(candidates) is defaultdict or type(candidates) is list:
        list_fp = []
        for c in candidates:
            list_fp.append(get_fpv(c, fpv_name, use_prior))
        return np.asarray(list_fp)
    # Do the same but for a single atoms object.
    else:
        c = candidates
        return np.asarray([get_fpv(c, fpv_name, use_prior)])


def get_fpv(c, fpv_name, use_prior):
    """ Get the fingerprint vector as an array from a single Atoms object.
        If a fingerprint vector is saved in info['data']['fpv'] it is returned
        otherwise saved in the data dictionary.
    """
    if len(fpv_name) == 1:
        if not use_prior:
            return fpv_name[0](atoms=c)
        if 'data' not in c.info:
            c.info['data'] = {'fpv': fpv_name[0](atoms=c)}
        elif 'fpv' not in c.info['data']:
            c.info['data']['fpv'] = fpv_name[0](atoms=c)
        return c.info['data']['fpv']
    if not use_prior:
        return concatenate_fpv(c, fpv_name)
    if 'data' not in c.info:
        c.info['data'] = {'fpv': concatenate_fpv(c, fpv_name)}
    elif 'fpv' not in c.info['data']:
        c.info['data']['fpv'] = concatenate_fpv(c, fpv_name)
    return c.info['data']['fpv']


def concatenate_fpv(c, fpv_name):
    """ Simple function to join multiple fingerprint vectors. """
    fpv = fpv_name[0](atoms=c)
    for i in fpv_name[1:]:
        fpv = np.concatenate((i(atoms=c), fpv))
    return fpv


def standardize(train, test=None):
    """ Standardize each descriptor in the FPV relative to the mean and
        standard deviation. If test data is supplied it is standardized
        relative to the training dataset.

        train: list
            List of atoms objects to be used as training dataset.

        test: list
            List of atoms objects to be used as test dataset.
    """
    std_fpv = []
    mean_fpv = []
    tt = np.transpose(train)
    for i in range(len(tt)):
        std_fpv.append(float(np.std(tt[i])))
        mean_fpv.append(float(np.mean(tt[i])))

    # Replace zero std with value 1 for devision.
    std_fpv = np.asarray(std_fpv)
    np.place(std_fpv, std_fpv == 0., [1.])

    std = defaultdict(list)
    for i in train:
        std['train'].append((i - mean_fpv) / std_fpv)
    if test is not None:
        for i in test:
            std['test'].append((i - mean_fpv) / std_fpv)
    std['std'] = std_fpv
    std['mean'] = mean_fpv

    return std


def normalize(train, test=None):
    """ Normalize each descriptor in the FPV to min/max or mean centered. If
        test data is supplied it is standardized relative to the training
        dataset.
    """
    max_fpv = []
    min_fpv = []
    mean_fpv = []
    tt = np.transpose(train)
    for i in range(len(tt)):
        max_fpv.append(float(max(tt[i])))
        min_fpv.append(float(min(tt[i])))
        mean_fpv.append(float(np.mean(tt[i])))
    dif = np.asarray(max_fpv) - np.asarray(min_fpv)

    # Replace zero difference with value 1 for devision.
    np.place(dif, dif == 0., [1.])

    norm = defaultdict(list)
    for i in train:
        norm['train'].append(np.asarray((i - np.asarray(mean_fpv)) / dif))
    if test is not None:
        for i in test:
            norm['test'].append(np.asarray((i - np.asarray(mean_fpv)) / dif))
    norm['mean'] = np.asarray(mean_fpv)
    norm['dif'] = dif

    return norm


def sure_independence_screening(target, train_fpv, size=None):
    """ Feature selection based on SIS discussed in Fan, J., Lv, J., J. R.
        Stat. Soc.: Series B, 2008, 70, 849.
    """
    select = defaultdict(list)
    std_x = standardize(train=train_fpv)
    std_t = target_standardize(target)

    p = np.shape(std_x['train'])[1]
    # NOTE: Magnitude is not scaled between -1 and 1
    omega = np.transpose(std_x['train']).dot(std_t['target']) / p

    order = list(range(np.shape(std_x['train'])[1]))
    sort_list = [list(i) for i in zip(*sorted(zip(abs(omega), order),
                                              key=lambda x: x[0],
                                              reverse=True))]

    select['sorted'] = sort_list[1]
    select['correlation'] = sort_list[0]
    if size is not None:
        select['accepted'] = sort_list[1][:size]
        select['rejected'] = sort_list[1][size:]

    return select