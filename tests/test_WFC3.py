# Last Updated: 2022-04-05

import sys
import os
import gc
from importlib import reload
import time as time_pkg

import pytest
import numpy as np

sys.path.insert(0, '..'+os.sep+'src'+os.sep)

TEST_DIR = os.path.dirname(os.path.realpath(__file__))

def WFC3(_capsys):
    from eureka.lib.readECF import MetaClass
    from eureka.lib.util import COMMON_IMPORTS, pathdirectory
    import eureka.lib.plots
    from eureka.S3_data_reduction import s3_reduce as s3
    from eureka.S4_generate_lightcurves import s4_genLC as s4
    try:
        import image_registration
        imported_image_registration = True
    except ModuleNotFoundError:
        imported_image_registration = False

    if not imported_image_registration:
        raise Exception("HST-relevant packages have not been installed,"
                        " so the WFC3 test is being skipped. You can install "
                        "all HST-related dependencies using "
                        "`pip install .[hst]`.")

    # Set up some parameters to make plots look nicer.
    # You can set usetex=True if you have LaTeX installed
    eureka.lib.plots.set_rc(style='eureka', usetex=False, filetype='.pdf')

    with _capsys.disabled():
        # is able to display any message without failing a test
        # useful to leave messages for future users who run the tests
        print("\n\nIMPORTANT: Make sure that any changes to the ecf files "
              "are\nincluded in demo ecf files and documentation "
              "(docs/source/ecf.rst).")
        print("\nWFC3 S3-4 test: ", end='', flush=True)

    # explicitly define meta variables to be able to run
    # pathdirectory fn locally
    meta = MetaClass()
    meta.eventlabel = 'WFC3'
    meta.datetime = time_pkg.strftime('%Y-%m-%d')
    meta.topdir = TEST_DIR
    ecf_path = os.path.join(TEST_DIR, 'WFC3_ecfs', '')

    reload(s3)
    reload(s4)
    s3_spec, s3_meta = s3.reduce(meta.eventlabel, ecf_path=ecf_path)
    s4_spec, s4_lc, s4_meta = s4.genlc(meta.eventlabel, ecf_path=ecf_path,
                                       s3_meta=s3_meta)

    # run assertions for S3
    meta.outputdir_raw = os.path.join('data', 'WFC3', 'Stage3', '')
    name = pathdirectory(meta, 'S3', 1, ap=5, bg=8)
    assert os.path.exists(name)
    assert os.path.exists(os.path.join(name, 'figs'))

    s3_cites = np.union1d(COMMON_IMPORTS[2], ["wfc3"])
    assert np.array_equal(s3_meta.citations, s3_cites)

    # run assertions for S4
    meta.outputdir_raw =  os.path.join('data', 'WFC3', 'Stage4', '')
    name = pathdirectory(meta, 'S4', 1, ap=5, bg=8)
    assert os.path.exists(name)
    assert os.path.exists(os.path.join(name, 'figs'))

    s4_cites = np.union1d(s3_cites, COMMON_IMPORTS[3])
    assert np.array_equal(s4_meta.citations, s4_cites)

    return True


def test_WFC3(capsys):
    
    # Run tests in an inner scope
    assert WFC3(capsys)
    gc.collect()

    # In the outerscope we can safely remove files without permission errors.
    # remove temporary files
    for i in range(1, 7):
        dir_path = os.path.join(TEST_DIR, 'data', 'WFC3', f'Stage{i}')
        if os.path.isdir(dir_path):
            for root, dirs, files in os.walk(dir_path, topdown=False):
                for file in files:
                    fp = os.path.join(root, file)
                    os.remove(fp)
                for dir_ in dirs:
                    os.rmdir(os.path.join(root, dir_))
            os.rmdir(dir_path)