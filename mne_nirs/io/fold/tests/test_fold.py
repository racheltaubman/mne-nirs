# -*- coding: utf-8 -*-
# Author: Robert Luke <mail@robertluke.net>
#
# License: BSD (3-clause)

from pathlib import Path
from shutil import copyfile

import numpy as np
import pandas as pd
import pytest

from mne.datasets.testing import data_path, requires_testing_data
from mne.io import read_raw_nirx
from mne.utils import check_version

from mne_nirs.io.fold._fold import _generate_montage_locations,\
    _find_closest_standard_location, _read_fold_xls
from mne_nirs.io import fold_landmark_specificity
from mne_nirs.io.fold import fold_channel_specificity

thisfile = Path(__file__).parent.resolve()
foldfile = thisfile / "data" / "example.xls"

# https://github.com/mne-tools/mne-testing-data/pull/72
fname_nirx_15_3_short = Path(data_path(download=False)) / \
    'NIRx' / 'nirscout' / 'nirx_15_3_recording'

requires_xlrd = pytest.mark.skipif(
    not check_version('xlrd', '1.0'), reason='Requires xlrd >= 1.0')


@requires_xlrd
@pytest.mark.parametrize('fold_files', (str, None, list))
def test_channel_specificity(monkeypatch, tmp_path, fold_files):
    raw = read_raw_nirx(fname_nirx_15_3_short, preload=True)
    raw.pick(range(2))
    kwargs = dict()
    n_want = 6
    if fold_files is list:
        kwargs = dict(fold_files=[foldfile])
    elif fold_files is str:
        kwargs = dict(fold_files=tmp_path)
        n_want *= 2
    else:
        assert fold_files is None
        monkeypatch.setenv('MNE_NIRS_FOLD_PATH', str(tmp_path))
        assert len(kwargs) == 0
        with pytest.raises(FileNotFoundError, match=r'fold_files\[0\] does.*'):
            fold_channel_specificity(raw)
        n_want *= 2
    copyfile(foldfile, tmp_path / '10-10.xls')
    copyfile(foldfile, tmp_path / '10-5.xls')
    res = fold_channel_specificity(raw, **kwargs)
    assert len(res) == 2
    assert res[0].shape == (n_want, 10)


@requires_xlrd
def test_landmark_specificity():
    raw = read_raw_nirx(fname_nirx_15_3_short, preload=True)
    res = fold_landmark_specificity(raw, "L Superior Frontal Gyrus",
                                    [foldfile])
    assert len(res) == len(raw.ch_names)
    assert np.max(res) <= 100
    assert np.min(res) >= 0


@requires_xlrd
def test_fold_workflow():
    # Read raw data
    raw = read_raw_nirx(fname_nirx_15_3_short, preload=True)
    reference_locations = _generate_montage_locations()
    channel_of_interest = raw.copy().pick(1)

    # Get source and detector labels
    source_locs = channel_of_interest.info['chs'][0]['loc'][3:6]
    source_label = _find_closest_standard_location(source_locs,
                                                   reference_locations)
    assert source_label == "T7"

    detector_locs = channel_of_interest.info['chs'][0]['loc'][6:9]
    detector_label = _find_closest_standard_location(detector_locs,
                                                     reference_locations)
    assert detector_label == "TP7"

    # Find correct fOLD elements
    tbl = _read_fold_xls(foldfile, atlas="Juelich")
    tbl = tbl.query("Source == @source_label").\
        query("Detector == @detector_label")

    # Query region of interest
    specificity = tbl.query("Landmark == 'L Mid Orbital Gyrus'")["Specificity"]
    assert specificity.values == 12.34


@requires_xlrd
def test_fold_reader():
    tbl = _read_fold_xls(foldfile, atlas="Juelich")
    assert isinstance(tbl, pd.DataFrame)
    assert tbl.shape == (11, 10)
    assert "L Superior Frontal Gyrus" in \
           list(tbl["Landmark"])


@requires_testing_data
def test_label_finder():
    """Test locating labels."""
    raw = read_raw_nirx(fname_nirx_15_3_short, preload=True)
    reference_locations = _generate_montage_locations()

    # Test central head position source
    raw_cz = raw.copy().pick(25)
    assert _find_closest_standard_location(
        raw_cz.info['chs'][0]['loc'][3:6],
        reference_locations) == "Cz"

    # Test right auditory position detector
    raw_cz = raw.copy().pick(4)
    assert _find_closest_standard_location(
        raw_cz.info['chs'][0]['loc'][6:9],
        reference_locations) == "T8"

    # Test right auditory position source
    raw_cz = raw.copy().pick(4)
    assert _find_closest_standard_location(
        raw_cz.info['chs'][0]['loc'][3:6],
        reference_locations) == "TP8"

    # Test left auditory position source
    raw_cz = raw.copy().pick(1)
    assert _find_closest_standard_location(
        raw_cz.info['chs'][0]['loc'][3:6],
        reference_locations) == "T7"

    # Test left auditory position detector
    raw_cz = raw.copy().pick(1)
    assert _find_closest_standard_location(
        raw_cz.info['chs'][0]['loc'][6:9],
        reference_locations) == "TP7"

    # Test rear position detector
    raw_cz = raw.copy().pick(9)
    assert _find_closest_standard_location(
        raw_cz.info['chs'][0]['loc'][6:9],
        reference_locations) == "PO2"
