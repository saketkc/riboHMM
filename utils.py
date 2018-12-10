from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import numpy as np
import re
from functools import reduce

READ_LENGTHS = [28, 29, 30, 31]
STARTCODONS = [
    'AUG', 'CUG', 'GUG', 'UUG', 'AAG', 'ACG', 'AGG', 'AUA', 'AUC', 'AUU'
]
STOPCODONS = ['UAA', 'UAG', 'UGA']

binarize = dict([(0, np.array([False, False, False])),
                 (1, np.array([False, False, True])),
                 (2, np.array([False, True, False])),
                 (3, np.array([False, True, True])),
                 (4, np.array([True, False, False])),
                 (5, np.array([True, False, True])),
                 (6, np.array([True, True, False])),
                 (7, np.array([True, True, True]))])

debinarize = dict([(val.tostring(), key) for key, val in binarize.items()])

# some essential functions
insum = lambda x, axes: np.apply_over_axes(np.sum, x, axes)
nplog = lambda x: np.nan_to_num(np.log(x))
andop = lambda x: reduce(lambda y, z: np.logical_and(y, z), x)
EPS = np.finfo(np.double).resolution
MAX = np.finfo(np.double).max
MIN = np.finfo(np.double).min

#nucleotide operations
DNA_COMPLEMENT = dict([('A', 'T'), ('T', 'A'), ('G', 'C'), ('C', 'G'),
                       ('N', 'N')])

make_complement = lambda seq: [DNA_COMPLEMENT[s] for s in seq]
make_reverse_complement = lambda seq: [DNA_COMPLEMENT[s] for s in seq][::-1]
makestr = lambda seq: ''.join(map(chr, seq))

CODON_AA_MAP = dict([('GCU','A'), ('GCC','A'), ('GCA','A'), ('GCG','A'), \
                 ('UGU','C'), ('UGC','C'), \
                 ('GAU','D'), ('GAC','D'), \
                 ('GAA','E'), ('GAG','E'), \
                 ('CGU','R'), ('CGC','R'), ('CGA','R'), ('CGG','R'), ('AGA','R'), ('AGG','R'), \
                 ('UUU','F'), ('UUC','F'), \
                 ('GGU','G'), ('GGC','G'), ('GGA','G'), ('GGG','G'), \
                 ('CAU','H'), ('CAC','H'), \
                 ('AAA','K'), ('AAG','K'), \
                 ('UUA','L'), ('UUG','L'), ('CUU','L'), ('CUC','L'), ('CUA','L'), ('CUG','L'), \
                 ('AUU','I'), ('AUC','I'), ('AUA','I'), \
                 ('AUG','M'), \
                 ('AAU','N'), ('AAC','N'), \
                 ('CCU','P'), ('CCC','P'), ('CCA','P'), ('CCG','P'), \
                 ('CAA','Q'), ('CAG','Q'), \
                 ('UCU','S'), ('UCC','S'), ('UCA','S'), ('UCG','S'), ('AGU','S'), ('AGC','S'), \
                 ('ACU','T'), ('ACC','T'), ('ACA','T'), ('ACG','T'), \
                 ('GUU','V'), ('GUC','V'), ('GUA','V'), ('GUG','V'), \
                 ('UGG','W'), \
                 ('UAU','Y'), ('UAC','Y'), \
                 ('UAA','X'), ('UGA','X'), ('UAG','X')])

translate = lambda seq: ''.join([CODON_AA_MAP[seq[s:s+3]] if seq[s:s+3] in CODON_AA_MAP else 'X' for s in range(0,len(seq),3)])


def make_cigar(mask):

    char = ['M', 'N']
    if np.all(mask):
        cigar = ['%dM' % mask.sum()]
    else:
        switches = list(np.where(np.logical_xor(mask[:-1], mask[1:]))[0] + 1)
        switches.insert(0, 0)
        cigar = [
            '%d%s' % (switches[i + 1] - switches[i], char[i % 2])
            for i in range(len(switches) - 1)
        ]
        cigar.append('%d%s' % (mask.size - switches[-1], char[(i + 1) % 2]))
    return ''.join(cigar)


def make_mask(cigar):

    intervals = list(map(int, re.split('[MN]', cigar)[:-1]))
    mask = np.zeros((np.sum(intervals), ), dtype='bool')
    for i, inter in enumerate(intervals[::2]):
        mask[np.sum(intervals[:2 * i]):np.sum(intervals[:2 * i]) +
             inter] = True
    return mask


def get_exons(mask):

    if np.all(mask):
        exons = ['1', '%d,' % mask.sum(), '0,']
    else:
        exons = [0, [], []]
        switches = list(np.where(np.logical_xor(mask[:-1], mask[1:]))[0] + 1)
        switches.insert(0, 0)
        exons[0] = '%d' % (len(switches[::2]))
        exons[2] = ','.join(map(str, switches[::2])) + ','
        exons[1] = ','.join(
            map(str, [
                switches[i + 1] - switches[i]
                for i in range(0,
                               len(switches) - 1, 2)
            ])) + ','
        exons[1] = exons[1] + '%d,' % (mask.size - switches[-1])
    return exons


def outsum(arr):
    """Summation over the first axis, without changing length of shape.

    Arguments
        arr : array

    Returns
        thesum : array

    .. note::
        This implementation is much faster than `numpy.sum`.

    """

    thesum = sum([a for a in arr])
    shape = [1]
    shape.extend(list(thesum.shape))
    thesum = thesum.reshape(tuple(shape))
    return thesum
