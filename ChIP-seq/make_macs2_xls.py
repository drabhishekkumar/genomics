#!/bin/env python
#
#     make_macs2_xls.py: Convert MACS output file to XLS spreadsheet
#     Copyright (C) University of Manchester 2013-2014 Peter Briggs, Ian Donaldson
#
########################################################################
#
# make_macs2_xls.py
#
#########################################################################

"""make_macs2_xls.py

Convert MACS output file to XLS spreadsheet

Given tab-delimited output from MACS, creates an XLS spreadsheet with
3 sheets: one containing the tabulated data plus extra columns derived
from that data (e.g. summit+/-100bps); one containing the header
information from the input; and one describing what each of the columns
in the data sheet are.

This is a modified version of make_macs_xls.py updated to work with
output from MACS 2.0.10.

"""

#######################################################################
# Import modules that this module depends on
#######################################################################

import os
import sys
import optparse
import logging
# Configure logging output
logging.basicConfig(format="%(levelname)s %(message)s")
# Put ../share onto Python search path for modules
SHARE_DIR = os.path.abspath(
    os.path.normpath(
        os.path.join(os.path.dirname(sys.argv[0]),'..','share')))
sys.path.append(SHARE_DIR)
from TabFile import TabFile
import simple_xls

import profile

#######################################################################
# Module metadata
#######################################################################

__version__ = '0.2.3'

#######################################################################
# Class definitions
#######################################################################

class MacsXLS:
    """Class for reading and manipulating XLS output from MACS

    Reads the XLS output file from the MACS peak caller and
    processes and stores the information for subsequent manipulation
    and output.

    To read in data from a MACS output file:

    >>> macs = MacsXLS("macs.xls")

    This reads in the data and prepends an additional 'order'
    column (a list of numbers from one to the number of data
    lines).

    To get the MACS version:

    >>> macs.macs_version
    2.0.10

    To access the 'header' information (as a Python list):

    >>> macs.header

    To see the column names (as a Python list):

    >>> macs.columns

    The data is stored as a TabFile object; to access the data
    use the 'data' property, e.g.

    >>> for line in macs.data:
    ...    print "Chr %s Start %s End" % (line['chr'],line['start'],line['end'])

    To sort the data on a particular column use the 'sort_on'
    method, e.g.

    >>> macs.sort_on('chr')

    (Note that the order column is always recalculated after
    sorting.)

    """

    def __init__(self,filen=None,fp=None,name=None):
        """Create a new MacsXLS instance

        Arguments:
          filen: name of the file to read the MACS output from.
            If None then fp argument must be supplied instead.
          fp: file-like object opened for reading. If None then
            filen argument must be supplied instead. If both filen
            and fp are supplied then fp will be used preferentially.

        """
        # Store data
        self.__filen = filen
        self.__name = name
        self.__macs_version = None
        self.__command_line = None
        self.__header = []
        self.__data = None
        # Open file, if necessary
        if fp is None:
            fp = open(filen,'r')
        else:
            filen = None
        # Iterate over header lines
        for line in fp:
            line = line.strip()
            if line.startswith('#') or line == '':
                # Header line
                self.__header.append(line)
                # Detect/extract data from header
                if line.startswith("# This file is generated by MACS version "):
                    # Look for MACS version
                    self.__macs_version = line.split()[8]
                elif self.__name is None and line.startswith("# name = "):
                    # Look for 'name' if none set
                    self.__name = line[len("# name = "):]
                elif line.startswith("# Command line: "):
                    # Look for command line
                    self.__command_line = line[16:]
            else:
                if self.__data is None:
                    # First line of actual data should be the column names
                    columns = line.split('\t')
                    # Insert an additional column called 'order'
                    columns.insert(0,"order")
                    # Set up TabFile to handle actual data
                    self.__data = TabFile(column_names=columns)
                else:
                    # Assume it's actual data and store it
                    self.__data.append(tabdata="\t%s" % line)
        # Close the file handle, if we opened it
        if filen is not None:
            fp.close()
        # Check that we actually got a version line
        if self.macs_version is None:
            raise Exception,"Failed to extract MACS version, not a MACS output file?"
        # Populate the 'order' column
        self.update_order()

    @property
    def filen(self):
        """Return the source file name

        """
        return self.__filen

    @property
    def name(self):
        """Return the name property

        """
        return self.__name

    @property
    def macs_version(self):
        """Return the MACS version extracted from the file

        """
        return self.__macs_version

    @property
    def command_line(self):
        """Return the command line string extracted from the header

        This is the value associated with the "# Command line: ..."
        header line.

        Will be 'None' if no matching header line is found, else is
        the string following the ':'.

        """
        return self.__command_line

    @property
    def columns(self):
        """Return the column names for the MACS data

        Returns a list of the column names from the data
        extracted from the file.

        """
        return self.__data.header()

    @property
    def columns_as_xls_header(self):
        """Returns the column name list, with hash prepended

        """
        return ['#'+self.columns[0]] + self.columns[1:]

    @property
    def header(self):
        """Return the header data from the file

        Returns a list of lines comprising the header
        extracted from the file.

        """
        return self.__header

    @property
    def data(self):
        """Return the data from the file

        Returns a TabFile object comprising the data
        extracted from the file.

        """
        return self.__data

    @property
    def with_broad_option(self):
        """Returns True if MACS was run with --broad option

        If --broad wasn't detected then returns False.

        """
        if self.macs_version.startswith('1.'):
            # Not an option in MACS 1.*
            return False
        try:
            # Was --broad specified in the command line?
            return '--broad' in self.command_line.split()
        except AttributeError:
            # No command line? Check for 'abs_summit' column
            return 'abs_summit' not in self.columns

    def sort_on(self,column,reverse=True):
        """Sort data on specified column

        Sorts the data in-place, by the specified column.

        By default data is sorted in descending order; set
        'reverse' argument to False to sort values in ascending
        order instead
 
        Note that the 'order' column is automatically updated
        after each sorting operation.

        Arguments:
          column: name of the column to sort on
          reverse: if True (default) then sort in descending
            order (i.e. largest to smallest). Otherwise sort in
            ascending order.

        """
        # Sort the data
        self.__data.sort(lambda line: line[column],reverse=reverse)
        # Update the 'order' column
        self.update_order()

    def update_order(self):
        # Set/update values in 'order' column
        for i in range(0,len(self.__data)):
            self.__data[i]['order'] = i+1

#######################################################################
# Functions
#######################################################################

def xls_for_macs2(macs_xls):
    """Create and return XLS workbook object for MACS2 output

    Arguments:
      macs_xls: populated MacsXLS object (must be from MACS2)

    Returns:
      simple_xls.XLSWorkBook

    """

    # Check MACS version - can't handle MACS 1.*
    if macs_xls.macs_version.startswith("1."):
        raise Exception,"Only handles output from MACS 2.0*"

    # Check --broad not specified
    if macs_xls.with_broad_option:
        raise Exception,"Handling --broad output not implemented"

    # Sort into order by fold_enrichment column
    macs_xls.sort_on('fold_enrichment',reverse=True)

    # Legnds text
    legends_text = """order\tSorting order FE
chr\tChromosome location of binding region
start\tStart coordinate of binding region
end\tEnd coordinate of binding region
summit-100\tSummit - 100bp
summit+100\tSummit + 100bp
summit-1\tSummit of binding region - 1
summit\tSummit of binding region
length\tLength of binding region
abs_summit\tCoordinate of region summit
pileup\tNumber of non-degenerate and position corrected reads at summit
-LOG10(pvalue)\tTransformed Pvalue -log10(Pvalue) for the binding region (e.g. if Pvalue=1e-10, then this value should be 10)
fold_enrichment\tFold enrichment for this region against random Poisson distribution with local lambda
-LOG10(qvalue)\tTransformed Qvalue -log10(Pvalue) for the binding region (e.g. if Qvalue=0.05, then this value should be 1.3)
"""

    # Create a new spreadsheet
    xls = simple_xls.XLSWorkBook()

    # Set up styles
    boldstyle = simple_xls.XLSStyle(bold=True)

    # Create the sheets
    #
    # data = the actual data from MACS
    data = xls.add_work_sheet('data',macs_xls.name)
    #
    # notes = the header data
    notes = xls.add_work_sheet('notes',"Notes")
    notes.write_row(1,text="MACS RUN NOTES:",style=boldstyle)
    notes.write_column('A',macs_xls.header,from_row=notes.next_row)
    notes.append_row(text="ADDITIONAL NOTES:",style=boldstyle)
    notes.append_row(text="By default regions are sorted by fold enrichment "
                     "(in descending order)")

    # legends = static text explaining the column headers
    legends = xls.add_work_sheet('legends',"Legends")
    legends.write_column('A',text=legends_text)

    # Add data to the "data" sheet
    data.write_row(1,data=macs_xls.columns_as_xls_header)
    for line in macs_xls.data:
        data.append_row(line)

    # Insert and populate formulae columns
    # Copy of chr column
    data.insert_column('E',text="chr")
    data.write_column('E',fill="=B?",from_row=2)
    # Summit-100
    data.insert_column('F',text="abs_summit-100")
    data.write_column('F',fill="=L?-100",from_row=2)
    # Summit+100
    data.insert_column('G',text="abs_summit+100")
    data.write_column('G',fill="=L?+100",from_row=2)
    # Copy of chr column
    data.insert_column('H',text="chr")
    data.write_column('H',fill="=B?",from_row=2)
    # Summit-1
    data.insert_column('I',text="summit-1")
    data.write_column('I',fill="=L?-1",from_row=2)
    # Summit
    data.insert_column('J',text="summit")
    data.write_column('J',fill="=L?",from_row=2)

    # Return spreadsheet object
    return xls

#######################################################################
# Tests
#######################################################################

import unittest
import cStringIO

MACS140beta_data = """# This file is generated by MACS version 1.4.0beta
# ARGUMENTS LIST:
# name = AS_Rb_Pmad_2_vs_Rb_PI_2_mfold_10-30_Plt1e-5_bw350_MACS14
# format = BED
# ChIP-seq file = solid0424_20101108_FRAG_BC_2_AS_COMBINED_F3_AS_Rb_Pmad_2.unique.csfasta.ma.50.5.bed
# control file = solid0424_20101108_FRAG_BC_2_AS_COMBINED_F3_AS_Rb_PI_2.unique.csfasta.ma.50.5.bed
# effective genome size = 1.20e+08
# band width = 350
# model fold = 10,30
# pvalue cutoff = 1.00e-05
# Range for calculating regional lambda is: 1000 bps and 10000 bps

# tag size is determined as 50 bps
# total tags in treatment: 9541851
# tags after filtering in treatment: 6005978
# maximum duplicate tags at the same position in treatment = 3
# Redundant rate in treatment: 0.37
# total tags in control: 10600387
# tags after filtering in control: 5190513
# maximum duplicate tags at the same position in control = 3
# Redundant rate in control: 0.51
# d = 200
chr	start	end	length	summit	tags	-10*log10(pvalue)	fold_enrichment	FDR(%)
chr2L	25639	29124	3486	2465	411	297.14	4.72	68.59
chr2L	66243	67598	1356	674	158	156.31	3.73	83.24
chr2L	88564	93752	5189	2934	933	1556.88	7.94	23.40
chr2L	99358	100787	1430	450	142	84.72	4.03	81.71
chr2L	248030	252120	4091	1126	621	129.90	3.97	86.04"""

MACS2010_20130419_data = """# This file is generated by MACS version 2.0.10.20130419 (tag:beta)
# ARGUMENTS LIST:
# name = Gli1_ChIP_vs_input_36bp_bowtie_mm10_BASE_mfold5,50_Pe-5_Q0.05_bw250_MACS2
# format = BED
# ChIP-seq file = ['Gli1_ChIP_NH1_36bp.fastq_bowtie_m1n2l28_mm10_random_chrM_chrUn_sorted_BASE.bed']
# control file = ['Gli1_Input_NH2_36bp.fastq_bowtie_m1n2l28_mm10_random_chrM_chrUn_sorted_BASE.bed']
# effective genome size = 1.87e+09
# band width = 250
# model fold = [5, 50]
# qvalue cutoff = 5.00e-02
# Larger dataset will be scaled towards smaller dataset.
# Range for calculating regional lambda is: 1000 bps and 10000 bps
# Broad region calling is off

# tag size is determined as 36 bps
# total tags in treatment: 22086203
# tags after filtering in treatment: 5306676
# maximum duplicate tags at the same position in treatment = 1
# Redundant rate in treatment: 0.76
# total tags in control: 24403248
# tags after filtering in control: 15259969
# maximum duplicate tags at the same position in control = 1
# Redundant rate in control: 0.37
# d = 148
# alternative fragment length(s) may be 148 bps
chr	start	end	length	abs_summit	pileup	-log10(pvalue)	fold_enrichment	-log10(qvalue)	name
chr1	11739723	11739870	148	11739812	7.00000	7.76684	5.62653	3.43962	Gli1_ChIP_vs_input_36bp_bowtie_mm10_BASE_mfold5,50_Pe-5_Q0.05_bw250_MACS2_peak_1
chr1	11969836	11970017	182	11969905	12.00000	14.83738	9.14312	9.72638	Gli1_ChIP_vs_input_36bp_bowtie_mm10_BASE_mfold5,50_Pe-5_Q0.05_bw250_MACS2_peak_2
chr1	12644697	12644846	150	12644743	8.00000	9.09804	6.32985	4.55480	Gli1_ChIP_vs_input_36bp_bowtie_mm10_BASE_mfold5,50_Pe-5_Q0.05_bw250_MACS2_peak_3
chr1	14307437	14307618	182	14307533	9.00000	10.15992	6.87334	5.55297	Gli1_ChIP_vs_input_36bp_bowtie_mm10_BASE_mfold5,50_Pe-5_Q0.05_bw250_MACS2_peak_4
chr1	14729977	14730124	148	14730003	9.00000	10.47462	7.03317	5.76536	Gli1_ChIP_vs_input_36bp_bowtie_mm10_BASE_mfold5,50_Pe-5_Q0.05_bw250_MACS2_peak_5"""

MACS2010_20131216_data = """# This file is generated by MACS version 2.0.10.20131216 (tag:beta)
# Command line: callpeak --treatment=NW-H3K27ac-chIP_E13.5_50bp_bowtie_m1n2l28_mm10_random_chrM_chrUn_sorted_BASE.bed --control=NW-H3K27ac-input_E13.5_50bp_bowtie_m1n2l28_mm10_random_chrM_chrUn_sorted_BASE.bed --name=NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_MACS2.0.10b --format=BED --gsize=mm --bw=300 --qvalue=0.05 --mfold 5 50
# ARGUMENTS LIST:
# name = NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_MACS2.0.10b
# format = BED
# ChIP-seq file = ['NW-H3K27ac-chIP_E13.5_50bp_bowtie_m1n2l28_mm10_random_chrM_chrUn_sorted_BASE.bed']
# control file = ['NW-H3K27ac-input_E13.5_50bp_bowtie_m1n2l28_mm10_random_chrM_chrUn_sorted_BASE.bed']
# effective genome size = 1.87e+09
# band width = 300
# model fold = [5, 50]
# qvalue cutoff = 5.00e-02
# Larger dataset will be scaled towards smaller dataset.
# Range for calculating regional lambda is: 1000 bps and 10000 bps
# Broad region calling is off

# tag size is determined as 50 bps
# total tags in treatment: 34761982
# tags after filtering in treatment: 25719667
# maximum duplicate tags at the same position in treatment = 1
# Redundant rate in treatment: 0.26
# total tags in control: 35952332
# tags after filtering in control: 32648707
# maximum duplicate tags at the same position in control = 1
# Redundant rate in control: 0.09
# d = 255
# alternative fragment length(s) may be 255 bps
chr	start	end	length	abs_summit	pileup	-log10(pvalue)	fold_enrichment	-log10(qvalue)	name
chr1	4785302	4786361	1060	4785978	31.00	19.45588	7.09971	16.36880	NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_MACS2.0.10b_peak_1
chr1	4857168	4857694	527	4857404	29.00	17.54599	6.65598	14.52698	NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_MACS2.0.10b_peak_2
chr1	4858211	4858495	285	4858423	18.00	8.17111	4.21545	5.55648	NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_MACS2.0.10b_peak_3
chr1	5082969	5083594	626	5083453	21.00	10.51344	4.88105	7.78195	NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_MACS2.0.10b_peak_4
chr1	6214126	6215036	911	6214792	56.00	47.04091	12.64636	43.11036	NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_MACS2.0.10b_peak_5"""

MACS2010_20131216_broad_data = """# This file is generated by MACS version 2.0.10.20131216 (tag:beta)
# Command line: callpeak --treatment=NW-H3K27ac-chIP_E13.5_50bp_bowtie_m1n2l28_mm10_random_chrM_chrUn_sorted_BASE.bed --control=NW-H3K27ac-input_E13.5_50bp_bowtie_m1n2l28_mm10_random_chrM_chrUn_sorted_BASE.bed --name=NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_broad_MACS2.0.10b --format=BED --gsize=mm --bw=300 --qvalue=0.05 --mfold 5 50 --broad --bdg
# ARGUMENTS LIST:
# name = NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_broad_MACS2.0.10b
# format = BED
# ChIP-seq file = ['NW-H3K27ac-chIP_E13.5_50bp_bowtie_m1n2l28_mm10_random_chrM_chrUn_sorted_BASE.bed']
# control file = ['NW-H3K27ac-input_E13.5_50bp_bowtie_m1n2l28_mm10_random_chrM_chrUn_sorted_BASE.bed']
# effective genome size = 1.87e+09
# band width = 300
# model fold = [5, 50]
# qvalue cutoff = 5.00e-02
# Larger dataset will be scaled towards smaller dataset.
# Range for calculating regional lambda is: 1000 bps and 10000 bps
# Broad region calling is on

# tag size is determined as 50 bps
# total tags in treatment: 34761982
# tags after filtering in treatment: 25719667
# maximum duplicate tags at the same position in treatment = 1
# Redundant rate in treatment: 0.26
# total tags in control: 35952332
# tags after filtering in control: 32648707
# maximum duplicate tags at the same position in control = 1
# Redundant rate in control: 0.09
# d = 255
# alternative fragment length(s) may be 255 bps
chr	start	end	length	pileup	-log10(pvalue)	fold_enrichment	-log10(qvalue)	name
chr1	4571604	4572035	432	11.81	4.00624	2.84289	1.70591	NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_broad_MACS2.0.10b_peak_1
chr1	4784978	4786450	1473	19.42	9.53551	4.45015	6.90879	NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_broad_MACS2.0.10b_peak_2
chr1	4857160	4858622	1463	18.48	8.80420	4.28339	6.20234	NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_broad_MACS2.0.10b_peak_3
chr1	5082969	5083609	641	16.57	7.03857	3.82006	4.50602	NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_broad_MACS2.0.10b_peak_4
chr1	6214118	6215462	1345	25.10	15.08276	5.78500	12.23221	NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_broad_MACS2.0.10b_peak_5"""

class TestMacsXLSForMacs140beta(unittest.TestCase):
    def test_load_macs14_xls_file(self):
        """Load data from MACS14 variant

        """
        macsxls = MacsXLS(fp=cStringIO.StringIO(MACS140beta_data))
        self.assertEqual(macsxls.macs_version,"1.4.0beta")
        self.assertEqual(macsxls.name,
                         "AS_Rb_Pmad_2_vs_Rb_PI_2_mfold_10-30_Plt1e-5_bw350_MACS14")
        self.assertEqual(macsxls.command_line,None)
        self.assertFalse(macsxls.with_broad_option)
        self.assertEqual(macsxls.columns,["order","chr","start","end","length","summit","tags",
                                          "-10*log10(pvalue)","fold_enrichment","FDR(%)"])
        self.assertEqual(len(macsxls.data),5)
        for i in range(0,5):
            self.assertEqual(macsxls.data[i]['order'],i+1)

    def test_sort_on_columns(self):
        """Check sorting for MACS14 variant data

        """
        macsxls = MacsXLS(fp=cStringIO.StringIO(MACS140beta_data))
        for line,value in zip(macsxls.data,(25639,66243,88564,99358,248030)):
            self.assertEqual(line['start'],value)
        macsxls.sort_on("start")
        for line,value in zip(macsxls.data,(248030,99358,88564,66243,25639)):
            self.assertEqual(line['start'],value)

class TestMacsXLSForMacs2010_20131216(unittest.TestCase):
    def test_load_macs2_xls_file(self):
        """Load data from MACS2.0.10.20131216

        """
        macsxls = MacsXLS(fp=cStringIO.StringIO(MACS2010_20131216_data))
        self.assertEqual(macsxls.macs_version,"2.0.10.20131216")
        self.assertEqual(macsxls.name,
                         "NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_MACS2.0.10b")
        self.assertEqual(macsxls.command_line,"callpeak --treatment=NW-H3K27ac-chIP_E13.5_50bp_bowtie_m1n2l28_mm10_random_chrM_chrUn_sorted_BASE.bed --control=NW-H3K27ac-input_E13.5_50bp_bowtie_m1n2l28_mm10_random_chrM_chrUn_sorted_BASE.bed --name=NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_MACS2.0.10b --format=BED --gsize=mm --bw=300 --qvalue=0.05 --mfold 5 50")
        self.assertFalse(macsxls.with_broad_option)
        self.assertEqual(macsxls.columns,["order","chr","start","end","length","abs_summit",
                                          "pileup",
                                          "-log10(pvalue)","fold_enrichment",
                                          "-log10(qvalue)","name"])
        self.assertEqual(len(macsxls.data),5)
        for i in range(0,5):
            self.assertEqual(macsxls.data[i]['order'],i+1)

    def test_sort_on_columns(self):
        """Check sorting for MACS2.0.10.20131216 data

        """
        macsxls = MacsXLS(fp=cStringIO.StringIO(MACS2010_20131216_data))
        for line,value in zip(macsxls.data,(31.00,29.00,18.00,21.00,56.00)):
            self.assertEqual(line['pileup'],value)
        macsxls.sort_on("pileup")
        for line,value in zip(macsxls.data,(56.00,31.00,29.00,21.00,18.00)):
            self.assertEqual(line['pileup'],value)

class TestMacsXLSForMacs2010_20131216_broad(unittest.TestCase):
    def test_load_macs2_xls_file(self):
        """Load data from MACS2.0.10.20131216 (--broad option)

        """
        macsxls = MacsXLS(fp=cStringIO.StringIO(MACS2010_20131216_broad_data))
        self.assertEqual(macsxls.macs_version,"2.0.10.20131216")
        self.assertEqual(macsxls.name,
                         "NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_broad_MACS2.0.10b")
        self.assertEqual(macsxls.command_line,"callpeak --treatment=NW-H3K27ac-chIP_E13.5_50bp_bowtie_m1n2l28_mm10_random_chrM_chrUn_sorted_BASE.bed --control=NW-H3K27ac-input_E13.5_50bp_bowtie_m1n2l28_mm10_random_chrM_chrUn_sorted_BASE.bed --name=NW-H3K27ac-chIP_vs_input_E13.5_50bp_bowtie_mm10_BASE_q0.05_bw300_mfold5to50_broad_MACS2.0.10b --format=BED --gsize=mm --bw=300 --qvalue=0.05 --mfold 5 50 --broad --bdg")
        self.assertTrue(macsxls.with_broad_option)
        self.assertEqual(macsxls.columns,["order","chr","start","end","length","pileup",
                                          "-log10(pvalue)","fold_enrichment",
                                          "-log10(qvalue)","name"])
        self.assertEqual(len(macsxls.data),5)
        for i in range(0,5):
            self.assertEqual(macsxls.data[i]['order'],i+1)

    def test_sort_on_columns(self):
        """Check sorting for MACS2.0.10.20131216 data (--broad option)

        """
        macsxls = MacsXLS(fp=cStringIO.StringIO(MACS2010_20131216_broad_data))
        for line,value in zip(macsxls.data,(11.81,19.42,18.48,16.57,25.10)):
            self.assertEqual(line['pileup'],value)
        macsxls.sort_on("pileup")
        for line,value in zip(macsxls.data,(25.10,19.42,18.48,16.57,11.81)):
            self.assertEqual(line['pileup'],value)

class TestMacsXLSForMacs2010_20130419(unittest.TestCase):
    def test_load_macs2_xls_file(self):
        """Load data from MACS2.0.10.20130419

        """
        macsxls = MacsXLS(fp=cStringIO.StringIO(MACS2010_20130419_data))
        self.assertEqual(macsxls.macs_version,"2.0.10.20130419")
        self.assertEqual(macsxls.name,
                         "Gli1_ChIP_vs_input_36bp_bowtie_mm10_BASE_mfold5,50_Pe-5_Q0.05_bw250_MACS2")
        self.assertEqual(macsxls.command_line,None)
        self.assertFalse(macsxls.with_broad_option)
        self.assertEqual(macsxls.columns,["order","chr","start","end","length","abs_summit",
                                          "pileup",
                                          "-log10(pvalue)","fold_enrichment",
                                          "-log10(qvalue)","name"])
        self.assertEqual(len(macsxls.data),5)
        for i in range(0,5):
            self.assertEqual(macsxls.data[i]['order'],i+1)

    def test_sort_on_columns(self):
        """Check sorting for MACS2.0.10.20130419 data

        """
        macsxls = MacsXLS(fp=cStringIO.StringIO(MACS2010_20130419_data))
        for line,value in zip(macsxls.data,(7.00000,12.00000,8.00000,9.00000,9.00000)):
            self.assertEqual(line['pileup'],value)
        macsxls.sort_on("pileup")
        for line,value in zip(macsxls.data,(12.00000,9.00000,9.00000,8.00000,7.00000)):
            self.assertEqual(line['pileup'],value)

class TestXlsForMacs2Function(unittest.TestCase):

    def test_xls_for_macs2_with_2010_20130419(self):
        """Generate XLSWorkBook for MACS2.0.10.20130419 data

        """
        macsxls = MacsXLS(fp=cStringIO.StringIO(MACS2010_20130419_data))
        xls = xls_for_macs2(macsxls)
        for sheet,title in zip(xls.worksheet,('data','notes','legends')):
            self.assertEqual(sheet,title)
        data = xls.worksheet['data']
        # Check header
        self.assertEqual(data['A1'],'#order')
        self.assertEqual(data['B1'],'chr')
        self.assertEqual(data['C1'],'start')
        self.assertEqual(data['D1'],'end')
        self.assertEqual(data['E1'],'chr')
        self.assertEqual(data['F1'],'abs_summit-100')
        self.assertEqual(data['G1'],'abs_summit+100')
        self.assertEqual(data['H1'],'chr')
        self.assertEqual(data['I1'],'summit-1')
        self.assertEqual(data['J1'],'summit')
        self.assertEqual(data['K1'],'length')
        self.assertEqual(data['L1'],'abs_summit')
        self.assertEqual(data['M1'],'pileup')
        self.assertEqual(data['N1'],'-log10(pvalue)')
        self.assertEqual(data['O1'],'fold_enrichment')
        self.assertEqual(data['P1'],'-log10(qvalue)')
        # Check first line of data
        self.assertEqual(data['A2'],1)
        self.assertEqual(data['B2'],'chr1')
        self.assertEqual(data['C2'],11969836)
        self.assertEqual(data['D2'],11970017)
        self.assertEqual(data.render_cell('E2'),'=B2')
        self.assertEqual(data.render_cell('F2'),'=L2-100')
        self.assertEqual(data.render_cell('G2'),'=L2+100')
        self.assertEqual(data.render_cell('H2'),'=B2')
        self.assertEqual(data.render_cell('I2'),'=L2-1')
        self.assertEqual(data.render_cell('J2'),'=L2')
        self.assertEqual(data['K2'],182)
        self.assertEqual(data['L2'],11969905)
        self.assertEqual(data['M2'],12)
        self.assertEqual(data['N2'],14.83738)
        self.assertEqual(data['O2'],9.14312)
        self.assertEqual(data['P2'],9.72638)
        # Check last line of data
        self.assertEqual(data['A6'],5)
        self.assertEqual(data['B6'],'chr1')
        self.assertEqual(data['C6'],11739723)
        self.assertEqual(data['D6'],11739870)
        self.assertEqual(data.render_cell('E6'),'=B6')
        self.assertEqual(data.render_cell('F6'),'=L6-100')
        self.assertEqual(data.render_cell('G6'),'=L6+100')
        self.assertEqual(data.render_cell('H6'),'=B6')
        self.assertEqual(data.render_cell('I6'),'=L6-1')
        self.assertEqual(data.render_cell('J6'),'=L6')
        self.assertEqual(data['K6'],148)
        self.assertEqual(data['L6'],11739812)
        self.assertEqual(data['M6'],7)
        self.assertEqual(data['N6'],7.76684)
        self.assertEqual(data['O6'],5.62653)
        self.assertEqual(data['P6'],3.43962)
        # Check order of fold enrichment column
        self.assertEqual(data['O2'],9.14312)
        self.assertEqual(data['O3'],7.03317)
        self.assertEqual(data['O4'],6.87334)
        self.assertEqual(data['O5'],6.32985)
        self.assertEqual(data['O6'],5.62653)

    def test_xls_for_macs2_with_2010_20131216(self):
        """Generate XLSWorkBook for MACS2.0.10.20131216 data

        """
        macsxls = MacsXLS(fp=cStringIO.StringIO(MACS2010_20131216_data))
        xls = xls_for_macs2(macsxls)
        for sheet,title in zip(xls.worksheet,('data','notes','legends')):
            self.assertEqual(sheet,title)
        data = xls.worksheet['data']
        # Check header
        self.assertEqual(data['A1'],'#order')
        self.assertEqual(data['B1'],'chr')
        self.assertEqual(data['C1'],'start')
        self.assertEqual(data['D1'],'end')
        self.assertEqual(data['E1'],'chr')
        self.assertEqual(data['F1'],'abs_summit-100')
        self.assertEqual(data['G1'],'abs_summit+100')
        self.assertEqual(data['H1'],'chr')
        self.assertEqual(data['I1'],'summit-1')
        self.assertEqual(data['J1'],'summit')
        self.assertEqual(data['K1'],'length')
        self.assertEqual(data['L1'],'abs_summit')
        self.assertEqual(data['M1'],'pileup')
        self.assertEqual(data['N1'],'-log10(pvalue)')
        self.assertEqual(data['O1'],'fold_enrichment')
        self.assertEqual(data['P1'],'-log10(qvalue)')
        # Check first line of data
        self.assertEqual(data['A2'],1)
        self.assertEqual(data['B2'],'chr1')
        self.assertEqual(data['C2'],6214126)
        self.assertEqual(data['D2'],6215036)
        self.assertEqual(data.render_cell('E2'),'=B2')
        self.assertEqual(data.render_cell('F2'),'=L2-100')
        self.assertEqual(data.render_cell('G2'),'=L2+100')
        self.assertEqual(data.render_cell('H2'),'=B2')
        self.assertEqual(data.render_cell('I2'),'=L2-1')
        self.assertEqual(data.render_cell('J2'),'=L2')
        self.assertEqual(data['K2'],911)
        self.assertEqual(data['L2'],6214792)
        self.assertEqual(data['M2'],56.00)
        self.assertEqual(data['N2'],47.04091)
        self.assertEqual(data['O2'],12.64636)
        self.assertEqual(data['P2'],43.11036)
        # Check last line of data
        self.assertEqual(data['A6'],5)
        self.assertEqual(data['B6'],'chr1')
        self.assertEqual(data['C6'],4858211)
        self.assertEqual(data['D6'],4858495)
        self.assertEqual(data.render_cell('E6'),'=B6')
        self.assertEqual(data.render_cell('F6'),'=L6-100')
        self.assertEqual(data.render_cell('G6'),'=L6+100')
        self.assertEqual(data.render_cell('H6'),'=B6')
        self.assertEqual(data.render_cell('I6'),'=L6-1')
        self.assertEqual(data.render_cell('J6'),'=L6')
        self.assertEqual(data['K6'],285)
        self.assertEqual(data['L6'],4858423)
        self.assertEqual(data['M6'],18.00)
        self.assertEqual(data['N6'],8.17111)
        self.assertEqual(data['O6'],4.21545)
        self.assertEqual(data['P6'],5.55648)
        # Check order of fold enrichment column
        self.assertEqual(data['O2'],12.64636)
        self.assertEqual(data['O3'],7.09971)
        self.assertEqual(data['O4'],6.65598)
        self.assertEqual(data['O5'],4.88105)
        self.assertEqual(data['O6'],4.21545)

    def test_xls_for_macs2_with_2010_20131216_broad(self):
        """Check 'xls_for_macs2' raises exception for MACS2.0.10.20131216 (--broad) data
        """
        macsxls = MacsXLS(fp=cStringIO.StringIO(MACS2010_20131216_broad_data))
        self.assertRaises(Exception,xls_for_macs2,macsxls)

    def test_xls_for_macs2_with_140beta(self):
        """Check 'xls_for_macs2' raises exception for MACS14 data
        """
        macsxls = MacsXLS(fp=cStringIO.StringIO(MACS140beta_data))
        self.assertRaises(Exception,xls_for_macs2,macsxls)

#######################################################################
# Main program
#######################################################################

def main(macs_file,xls_out):
    """Driver function

    Wraps core functionality of program to facilitate
    performance profiling
    
    Arguments:
      macs_file: output .xls file from MACS peak caller
      xls_out: name to write output XL spreadsheet file to
    
    """

    # Load the data from the file
    macs_xls = MacsXLS(macs_file)
    if macs_xls.macs_version is None:
        logging.error("couldn't detect MACS version")
        sys.exit(1)
    else:
        print "Input file is from MACS %s" % macs_xls.macs_version

    # Create XLS file
    try:
        xls = xls_for_macs2(macs_xls)
    except Exception,ex:
        logging.error("failed to convert to XLS: %s" % ex)
        sys.exit(1)
    xls.save_as_xls(xls_out)

if __name__ == "__main__":
    # Process command line
    p = optparse.OptionParser(usage="%prog <MACS2_OUTPUT> [ <XLS_OUT> ]",
                              version=__version__,
                              description=
                              "Create an XLS spreadsheet from the output of version 2.0.10 "
                              "of the MACS peak caller. <MACS2_OUTPUT> is the output '.xls' "
                              "file from MACS2; if supplied then <XLS_OUT> is the name to use "
                              "for the output file, otherwise it will be called "
                              "'XLS_<MACS2_OUTPUT>.xls'.")
    options,args = p.parse_args()
    # Get input file name
    if len(args) < 1 or len(args) > 2:
        p.error("Wrong number of arguments")
    macs_in = args[0]

    # Build output file name: if not explicitly supplied on the command
    # line then use "XLS_<input_name>.xls"
    if len(args) == 2:
        xls_out = args[1]
    else:
        # MACS output file might already have an .xls extension
        # but we'll add an explicit .xls extension
        xls_out = "XLS_"+os.path.splitext(os.path.basename(macs_in))[0]+".xls"
    print "Input file: %s" % macs_in
    print "Output XLS: %s" % xls_out
    ##profile.run("main(macs_in,xls_out)")
    main(macs_in,xls_out)

