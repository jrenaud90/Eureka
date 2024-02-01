# Last Updated: 2022-04-05

import sys
import os
import gc
from importlib import reload
import time as time_pkg

import numpy as np

sys.path.insert(0, '..'+os.sep+'src'+os.sep)

TEST_DIR = os.path.dirname(os.path.realpath(__file__))

def NIRSpec(_capsys):
    from eureka.lib.readECF import MetaClass
    from eureka.lib.util import COMMON_IMPORTS, pathdirectory
    import eureka.lib.plots
    try:
        from eureka.S2_calibrations import s2_calibrate as s2
    except ModuleNotFoundError:
        pass
    from eureka.S3_data_reduction import s3_reduce as s3
    from eureka.S4_generate_lightcurves import s4_genLC as s4
    from eureka.S5_lightcurve_fitting import s5_fit as s5

    # Set up some parameters to make plots look nicer.
    # You can set usetex=True if you have LaTeX installed
    eureka.lib.plots.set_rc(style='eureka', usetex=False, filetype='.png')

    s2_installed = 'eureka.S2_calibrations.s2_calibrate' in sys.modules
    if not s2_installed:
        with _capsys.disabled():
            print("\n\nIMPORTANT: Make sure that any changes to the ecf files "
                  "are\nincluded in demo ecf files and documentation "
                  "(docs/source/ecf.rst).\nSkipping MIRI Stage 2 test as "
                  "could not import eureka.S2_calibrations.s2_calibrate.")
            print("\nNIRSpec S3-5 test: ", end='', flush=True)
    else:
        with _capsys.disabled():
            # is able to display any message without failing a test
            # useful to leave messages for future users who run the tests
            print("\n\nIMPORTANT: Make sure that any changes to the ecf files "
                  "are\nincluded in demo ecf files and documentation "
                  "(docs/source/ecf.rst).")
            print("\nNIRSpec S2-5 test: ", end='', flush=True)

    # explicitly define meta variables to be able to run
    # pathdirectory fn locally
    meta = MetaClass()
    meta.eventlabel = 'NIRSpec'
    meta.datetime = time_pkg.strftime('%Y-%m-%d')
    meta.topdir = TEST_DIR
    ecf_path = os.path.join(TEST_DIR, 'NIRSpec_ecfs', '')

    if s2_installed:
        # Only run S2 stuff if jwst package has been installed
        reload(s2)
    reload(s3)
    reload(s4)
    reload(s5)
    if s2_installed:
        # Only run S2 stuff if jwst package has been installed
        s2_meta = s2.calibrateJWST(meta.eventlabel, ecf_path=ecf_path)
        
        s2_cites = np.union1d(COMMON_IMPORTS[1], ["nirspec"])
        assert np.array_equal(s2_meta.citations, s2_cites)

        s3_cites = np.union1d(s2_cites, COMMON_IMPORTS[2])
    else:
        s2_meta = None
        s3_cites = np.union1d(COMMON_IMPORTS[2], ["nirspec"])

    s3_spec, s3_meta = s3.reduce(meta.eventlabel, ecf_path=ecf_path,
                                 s2_meta=s2_meta)
    s4_spec, s4_lc, s4_meta = s4.genlc(meta.eventlabel, ecf_path=ecf_path,
                                       s3_meta=s3_meta)
    s5_meta = s5.fitlc(meta.eventlabel, ecf_path=ecf_path, s4_meta=s4_meta)
    # run assertions for S2
    if s2_installed:
        # Only run S2 stuff if jwst package has been installed
        meta.outputdir_raw = os.path.join('data', 'JWST-Sim', 'NIRSpec', 'Stage2', '')
        name = pathdirectory(meta, 'S2', 1)
        assert os.path.exists(name)
        assert os.path.exists(os.path.join(name, 'figs'))

    # run assertions for S3
    meta.outputdir_raw = os.path.join('data', 'JWST-Sim', 'NIRSpec', 'Stage3', '')
    name = pathdirectory(meta, 'S3', 1, ap=8, bg=10)
    assert os.path.exists(name)
    assert os.path.exists(os.path.join(name, 'figs'))

    assert np.array_equal(s3_meta.citations, s3_cites)

    # run assertions for S4
    meta.outputdir_raw = os.path.join('data', 'JWST-Sim', 'NIRSpec', 'Stage4', '')
    name = pathdirectory(meta, 'S4', 1, ap=8, bg=10)
    assert os.path.exists(name)
    assert os.path.exists(os.path.join(name, 'figs'))

    s4_cites = np.union1d(s3_cites, COMMON_IMPORTS[3])
    assert np.array_equal(s4_meta.citations, s4_cites)

    # run assertions for S5
    meta.outputdir_raw = os.path.join('data', 'JWST-Sim', 'NIRSpec', 'Stage5', '')
    name = pathdirectory(meta, 'S5', 1, ap=8, bg=10)
    assert os.path.exists(name)
    assert os.path.exists(os.path.join(name, 'figs'))

    s5_cites = np.union1d(s4_cites, COMMON_IMPORTS[4] + ["batman"])
    assert np.array_equal(s5_meta.citations, s5_cites)

    return True

def test_NIRSpec(capsys):
    
    # Run tests in an inner scope
    assert NIRSpec(capsys)
    gc.collect()

    # In the outerscope we can safely remove files without permission errors.
    # remove temporary files
    for i in range(1, 7):
        dir_path = os.path.join(TEST_DIR, 'data', 'JWST-Sim', 'NIRSpec', f'Stage{i}')
        if os.path.isdir(dir_path):
            for root, dirs, files in os.walk(dir_path, topdown=False):
                for file in files:
                    fp = os.path.join(root, file)
                    os.remove(fp)
                for dir_ in dirs:
                    os.rmdir(os.path.join(root, dir_))
            os.rmdir(dir_path)
