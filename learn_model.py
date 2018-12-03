import argparse
import pickle
import warnings
import pdb

import numpy as np

import load_data
import ribohmm
import seq
import utils

# ignore warnings with these expressions
warnings.filterwarnings('ignore', '.*overflow encountered.*',)
warnings.filterwarnings('ignore', '.*divide by zero.*',)
warnings.filterwarnings('ignore', '.*invalid value.*',)

def parse_args():
    parser = argparse.ArgumentParser(description=" learns the parameters of riboHMM to infer translation "
                                     " from ribosome profiling data and RNA sequence data; "
                                    " RNA-seq data can also be used if available ")

    parser.add_argument("--restarts",
                        type=int,
                        default=1,
                        help="number of re-runs of the algorithm (default: 1)")

    parser.add_argument("--mintol",
                        type=float,
                        default=1e-4,
                        help="convergence criterion for change in per-base marginal likelihood (default: 1e-4)")

    parser.add_argument("--scale_beta",
                        type=float,
                        default=10000.,
                        help="scaling factor for initial precision values (default: 1e4)")

    parser.add_argument("--batch",
                        type=int,
                        default=1000,
                        help="number of transcripts used for learning model parameters (default: 1000)")

    parser.add_argument("--model_file",
                        type=str,
                        default=None,
                        help="output file name to store the model parameters")

    parser.add_argument("--log_file",
                        type=str,
                        default=None,
                        help="file name to store some statistics of the EM algorithm ")

    parser.add_argument("--rnaseq_file",
                        type=str,
                        default=None,
                        help="prefix of tabix file with counts of RNA-seq reads")

    parser.add_argument("--mappability_file",
                        type=str,
                        default=None,
                        help="prefix of tabix file with mappability information")

    parser.add_argument("fasta_file",
                        action="store",
                        help="fasta file containing the genome sequence")

    parser.add_argument("gtf_file",
                        action="store",  
                        help="gtf file containing the assembled transcript models")

    parser.add_argument("riboseq_file",
                        action="store",
                        help="prefix of tabix files with counts of ribosome footprints")

    options = parser.parse_args()

    return options

def select_transcripts(options):
    
    # load all transcripts
    transcript_models_dict = load_data.load_gtf(options.gtf_file)
    transcript_models = list(transcript_models_dict.values())
    T = len(transcript_models)

    # get translation level in all transcripts
    ribo_track = load_data.RiboSeq(options.riboseq_file)
    transcript_translation_rate = [c/float(t.mask.sum()) for c,t in 
        zip(ribo_track.get_total_counts(transcript_models), transcript_models)]

    # select top transcripts
    transcripts = []
    transcript_bounds = dict()
    order = np.argsort(transcript_translation_rate)[::-1]
    for index in order:
        transcript = transcript_models[index]
 
        # check if all exons have at least 5 footprints
        exon_counts = ribo_track.get_exon_total_counts([transcript])[0]
        if np.any(exon_counts<5):
            continue

        # check if transcript overlaps any previous transcript
        # filter out strict overlaps
        overlap = False
        try:
            for bound in transcript_bounds[transcript.chromosome]:
                if not (transcript.stop<bound[0] or transcript.start>bound[1]):
                    overlap = True
                    break
        except KeyError:
            pass
        if overlap:
            continue

        transcripts.append(transcript)
        try:
            transcript_bounds[transcript.chromosome].append([transcript.start, transcript.stop])
        except KeyError:
            transcript_bounds[transcript.chromosome] = [[transcript.start, transcript.stop]]

        # select fixed number of transcripts for learning
        if len(transcripts)>=options.batch:
            break

    return transcripts

def learn(options):

    # select transcripts for learning parameters
    transcripts = select_transcripts(options)
    T = len(transcripts)
    print("%d transcripts selected"%T)

    # load sequence of transcripts and transform sequence data
    genome_track = load_data.Genome(options.fasta_file, options.mappability_file)
    codon_flags = []
    total_bases = 0
    for rna_sequence in genome_track.get_sequence(transcripts):
        sequence = seq.RnaSequence(rna_sequence)
        codon_flags.append(sequence.mark_codons())
        total_bases += len(rna_sequence)
    print("%d bases covered"%total_bases)

    # load footprint count data in transcripts
    ribo_track = load_data.RiboSeq(options.riboseq_file)
    footprint_counts = ribo_track.get_counts(transcripts)
    ribo_track.close()
    for i,r in enumerate(utils.READ_LENGTHS):
        print("%d ribosome footprints of length %d bp"%(np.sum([c[:,i].sum() for c in footprint_counts]),r))

    # load transcript-level rnaseq RPKM
    if options.rnaseq_file is None:
        rna_counts = np.ones((T,), dtype='float')
    else:
        rnaseq_track = load_data.RnaSeq(options.rnaseq_file)
        rna_counts = rnaseq_track.get_total_counts(transcripts)
        rnaseq_track.close()
    print("median RNA-seq RPKM in data is %.2e"%(np.sum(rna_counts)))

    # load mappability of transcripts; transform mappability to missingness
    if options.mappability_file is not None:
        rna_mappability = genome_track.get_mappability(transcripts)
    else:
        rna_mappability = [np.ones(c.shape,dtype='bool') for c in footprint_counts]
    genome_track.close()
    for i,r in enumerate(utils.READ_LENGTHS):
        print("%d bases have missing counts for %d bp footprints"%(np.sum([m.shape[0]-np.sum(m[:,i]) for m in rna_mappability]),r))

    # run the learning algorithm
    transition, emission, L = ribohmm.learn_parameters(footprint_counts, codon_flags, \
                           rna_counts, rna_mappability, options.scale_beta, \
                           options.restarts, options.mintol)

    # output model parameters
    handle = open(options.model_file,'w')
    pickle.Pickler(handle,protocol=2).dump(transition)
    pickle.Pickler(handle,protocol=2).dump(emission)
    handle.close()

if __name__=="__main__":

    options = parse_args()

    learn(options)
