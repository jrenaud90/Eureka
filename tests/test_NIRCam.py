# Last Updated: 2022-04-05

import sys
import os
import gc
from importlib import reload
import time as time_pkg

import numpy as np

sys.path.insert(0, '..'+os.sep+'src'+os.sep)

TEST_DIR = os.path.dirname(os.path.realpath(__file__))

def NIRCam(_capsys):
    from eureka.lib.readECF import MetaClass
    from eureka.lib.util import COMMON_IMPORTS, pathdirectory
    import eureka.lib.plots
    # try:
    #     from eureka.S2_calibrations import s2_calibrate as s2
    # except ModuleNotFoundError:
    #     pass
    from eureka.S3_data_reduction import s3_reduce as s3
    from eureka.S4_generate_lightcurves import s4_genLC as s4
    from eureka.S5_lightcurve_fitting import s5_fit as s5
    from eureka.S6_planet_spectra import s6_spectra as s6

    # Set up some parameters to make plots look nicer.
    # You can set usetex=True if you have LaTeX installed
    eureka.lib.plots.set_rc(style='eureka', usetex=False, filetype='.png')

    with _capsys.disabled():
        # is able to display any message without failing a test
        # useful to leave messages for future users who run the tests
        print("\n\nIMPORTANT: Make sure that any changes to the ecf files "
              "are\nincluded in demo ecf files and documentation "
              "(docs/source/ecf.rst).")
        print("\nNIRCam S3-6 test: ", end='', flush=True)

    # explicitly define meta variables to be able to run
    # pathdirectory fn locally
    meta = MetaClass()
    meta.eventlabel = 'NIRCam'
    meta.datetime = time_pkg.strftime('%Y-%m-%d')
    meta.topdir = TEST_DIR
    ecf_path = os.path.join(TEST_DIR, 'NIRCam_ecfs', '')

    reload(s3)
    reload(s4)
    reload(s5)
    reload(s6)

    s3_spec, s3_meta = s3.reduce(meta.eventlabel, ecf_path=ecf_path)
    s4_spec, s4_lc, s4_meta = s4.genlc(meta.eventlabel, ecf_path=ecf_path,
                                       s3_meta=s3_meta)
    s5_meta = s5.fitlc(meta.eventlabel, ecf_path=ecf_path, s4_meta=s4_meta)
    s6_meta = s6.plot_spectra(meta.eventlabel, ecf_path=ecf_path,
                              s5_meta=s5_meta)

    # run assertions for S3
    meta.outputdir_raw = os.path.join('data', 'JWST-Sim', 'NIRCam', 'Stage3', '')
    name = pathdirectory(meta, 'S3', 1, ap=8, bg=12)
    assert os.path.exists(name)
    assert os.path.exists(os.path.join(name, 'figs'))

    s3_cites = np.union1d(COMMON_IMPORTS[2], ["nircam"])
    assert np.array_equal(s3_meta.citations, s3_cites)

    # run assertions for S4
    meta.outputdir_raw = os.path.join('data', 'JWST-Sim', 'NIRCam', 'Stage4', '')
    name = pathdirectory(meta, 'S4', 1, ap=8, bg=12)
    assert os.path.exists(name)
    assert os.path.exists(os.path.join(name, 'figs'))

    s4_cites = np.union1d(s3_cites, COMMON_IMPORTS[3])
    assert np.array_equal(s4_meta.citations, s4_cites)

    # run assertions for S5
    meta.outputdir_raw = os.path.join('data', 'JWST-Sim', 'NIRCam', 'Stage5', '')
    name = pathdirectory(meta, 'S5', 1, ap=8, bg=12)
    assert os.path.exists(name)
    assert os.path.exists(os.path.join(name, 'figs'))

    s5_cites = np.union1d(s4_cites, COMMON_IMPORTS[4] +
                          ["emcee", "dynesty", "batman"])
    assert np.array_equal(s5_meta.citations, s5_cites)

    # run assertions for S6
    meta.outputdir_raw = os.path.join('data', 'JWST-Sim', 'NIRCam', 'Stage6', '')
    name = pathdirectory(meta, 'S6', 1, ap=8, bg=12)
    assert os.path.exists(name)
    assert os.path.exists(os.path.join(name, 'figs'))

    s6_cites = np.union1d(s5_cites, COMMON_IMPORTS[5])
    assert np.array_equal(s6_meta.citations, s6_cites)

    return True

def test_NIRCam(capsys):
    
    # Run tests in an inner scope
    assert NIRCam(capsys)
    gc.collect()

    # In the outerscope we can safely remove files without permission errors.
    # remove temporary files
    for i in range(1, 7):
        dir_path = os.path.join(TEST_DIR, 'data', 'JWST-Sim', 'NIRCam', f'Stage{i}')
        if os.path.isdir(dir_path):
            for root, dirs, files in os.walk(dir_path, topdown=False):
                for file in files:
                    fp = os.path.join(root, file)
                    os.remove(fp)
                for dir_ in dirs:
                    os.rmdir(os.path.join(root, dir_))
            os.rmdir(dir_path)
