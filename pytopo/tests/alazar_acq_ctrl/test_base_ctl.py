import pytest

from pytopo.rf.alazar.acquisition_controllers import BaseAcqCtl


@pytest.fixture(scope='function')
def simulated_base_acq_ctl(simulated_alazar):
    acq_ctl = None

    try:
        acq_ctl = BaseAcqCtl('base_acq_ctl', simulated_alazar.name)

        yield acq_ctl

    finally:
        if acq_ctl is not None:
            acq_ctl.close()


def test_smth(simulated_base_acq_ctl):
    alazar = simulated_base_acq_ctl._alazar

    with alazar.syncing():
        alazar.sample_rate(1e6)

    data = simulated_base_acq_ctl.acquisition()

    assert data.shape == (1, 2)
