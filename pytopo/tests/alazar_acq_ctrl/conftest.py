import pytest
from qcodes.instrument_drivers.AlazarTech.ATS9360 import AlazarTech_ATS9360

from .simulated_alazar_ats_api import SimulatedAlazarATSAPI


@pytest.fixture(scope='function')
def simulated_alazar():
    driver = None

    try:
        driver = AlazarTech_ATS9360(
            'Alazar',
            api=SimulatedAlazarATSAPI(dll_path='simulated'))

        yield driver

    finally:
        if driver is not None:
            driver.close()
