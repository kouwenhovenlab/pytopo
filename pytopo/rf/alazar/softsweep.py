import time
import numpy as np

import qcodes

from . import acquisition_controllers
from .awg_sequences import TriggerSequence


class SoftSweepCtl(acquisition_controllers.PostIQCtl):
    """
    An acquisition controller that allows fast software spec.
    The frequencies can be iterated through without stopping the alazar acquisition.
    Returns one IQ value per frequency.

    NOTE: you probably want to use at least 2 or 3 averages per point for this to work
    without glitches.

    Set the total number of buffers, and the buffers per block to determine the number of points
    and the number of averages, n_avgs = buffers / buffers_per_block.

    You will want to run this when the AWG runs a sequence that triggers the alazar n_avgs times in a row,
    but each of these trigger trains must be triggered (i.e., AWG is waiting for a trigger).
    Of course the trigger interval needs to slightly exceed the acquisition time per record, as usual.

    For determining how to advance from one sweep point to the next, you can specify the function
    ``next_point_trigger_func()``. Per default this does nothing, but the user can set it to a
    function that could play a trigger on the AWG. This depends on thow the setup is hooked up.
    """

    sweep_vals = np.array([])
    sweep_param = qcodes.Parameter('dummy_parameter', set_cmd=None)
    settling_time = 0
    verbose = True

    @staticmethod
    def next_point_trigger_func(): return None

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

        self._step = 0

    def _settle(self):
        if self.settling_time > 0:
            time.sleep(self.settling_time)

    def _perform_step(self, num):
        """
        Set generator to the i-th point whenever buffer_number // buffers_per_block increases.
        Takes into account that calls to this function lag 2 behind the actual acquisition.
        """
        t0 = time.perf_counter()
        awg = qcodes.Station.default.awg

        # we have to increase num by 2: by the time this is called, the
        # alazar is already measuring the buffer that's 2 after the received one.
        # this is just a reality of the alazar we have to live with here.
        if ((num+2) % self.buffers_per_block()) == 0:
            self._step += 1
            if self._step < len(self.sweep_vals):
                if self.verbose:
                    print(f'Point {self._step + 1} ({self.sweep_vals[self._step]:1.5e})'
                          + 10 * "", end='\r')
                self.sweep_param(self.sweep_vals[self._step])
                self._settle()
            else:
                if self.verbose:
                    print('Done!', end='\r')

            self.next_point_trigger_func()

        self.step_times[num] = (time.perf_counter() - t0)*1e3

    def pre_acquire(self):
        """
        Starts the acquisition. Sets the generator to the first point, triggers the AWG for the first time.
        """
        super().pre_acquire()

        self.step_times = np.zeros(self.buffers_per_acquisition(), dtype=float)
        self.sweep_param(self.sweep_vals[0])
        self._settle()

        self._step = 0
        self.next_point_trigger_func()

    def buffer_done_callback(self, buffernum):
        """
        This function is called every time the alazar returns buffer data.
        """
        nextstep = buffernum
        self._perform_step(nextstep)


def setup_triggered_softsweep(controller, sweep_param, sweep_vals, integration_time,
                              time_bin=0.5e-3, setup_awg=True, verbose=True, 
                              post_integration_delay=10e-6):
    """
    Set up a triggered softsweep.
    
    :param controller: the soft sweep acquisition controller to use. User has to specify
                       the controllers trigger function.
    :param sweep_param: parameter that the softsweep is sweeping over.
    :param sweep_vals: values to sweep over.
    :param integration_time: total integration time per point [s]
    :param time_bin: size of the chunks we divide the integration time up in [s]
                     this will be the size of a single alazar buffer.
                     number of averages per point will be set based on that.
    :param setup_awg: if True, program the awg.
    :param verbose: if True, print Alazar setup info.
    :param post_integration_delay: delay between end of integration and next trigger [s]
    """
    
    # checks
    if integration_time // time_bin < 3:
        raise ValueError('integration time should be at least 3 times longer than the time bin.')
    
    station = qcodes.Station.default
    
    npts = len(sweep_vals)
    navgs = int(integration_time // time_bin)
    nbufs = navgs * npts
    
    # setting up the AWG
    if setup_awg:
        seq = TriggerSequence(station.awg, SR=1e7)
        seq.wait = 'first'
        seq.setup_awg(cycle_time=(time_bin + post_integration_delay), nreps_per_cycle=navgs)
        
    controller.verbose = True
    controller.sweep_param = sweep_param
    controller.sweep_vals = sweep_vals
    controller.buffers_per_block(navgs)
    controller.average_buffers(True)
    controller.setup_acquisition(
        samples = None,
        records = 1,
        buffers = nbufs,
        acq_time = time_bin,
        allocated_buffers = navgs,
        verbose = verbose,
    )
    
def measure_triggered_softsweep(controller, sweep_param, sweep_vals, integration_time, 
                                exp_name=None, channel=0, **kw):
    """
    Set up and measure a single triggered softsweep trace.
    
    :param controller: softsweep controller to use
    :param sweep_param: qcodes parameter to sweep over
    :param sweep_vals: values for the sweep
    :param integration_time: total integration time per point [s]
    :param exp_name: name of the experiment. if ``None``, determine one automatically.
    :param channel: Alazar channel that contains the data.

    :return: qcodes dataset
    
    kws will be passed to ``setup_triggered_softsweep``.
    """

    station = qcodes.Station.default
    sample = qcodes.config.user.get('current_sample')    
    if exp_name is None:
        exp_name = f'{sweep_param.full_name}_triggered_softsweep'
    
    exp = qcodes.load_or_create_experiment(exp_name, sample)
    meas = qcodes.Measurement(exp, station)
    
    independents = [sweep_param]
    meas.register_parameter(sweep_param, paramtype='array')
    meas.register_custom_parameter('amplitude', unit='V', setpoints=independents, 
                                   paramtype='array')
    meas.register_custom_parameter('phase', unit='rad', setpoints=independents,
                                   paramtype='array')
    
    with meas.run() as datasaver:
        setup_triggered_softsweep(controller, sweep_param, sweep_vals, integration_time,
                                  setup_awg=True, verbose=True, **kw)
        data = np.squeeze(controller.acquisition())[..., channel]

        result = []
        result.append((sweep_param, sweep_vals))
        result.append(('amplitude', np.abs(data)))
        result.append(('phase', np.angle(data)))
        datasaver.add_result(*result)
    
    return datasaver.dataset

def measure_triggered_softsweep_vs_parameter(controller, sweep_param, sweep_vals, integration_time,
                                             parameter, values,
                                             exp_name=None, channel=0, **kw):
    """
    Set up and measure a series of triggered softsweep, iterating over an
    additional parameter.
    
    :param controller: softsweep controller to use
    :param sweep_param: qcodes parameter to sweep over
    :param sweep_vals: values for the sweep
    :param integration_time: total integration time per point [s]
    :param parameter: additional qcodes parameter to iterate over (as an outer loop)
    :param values: values for the additional parameter
    :param exp_name: name of the experiment. if ``None``, determine one automatically
    :param channel: Alazar channel that contains the data

    :return: qcodes dataset
    
    kws will be passed to ``setup_triggered_softsweep``.
    """
    station = qcodes.Station.default
    sample = qcodes.config.user.get('current_sample')    
    if exp_name is None:
        exp_name = f'{sweep_param.full_name}_triggered_softsweep'
    
    exp = qcodes.load_or_create_experiment(exp_name, sample)
    meas = qcodes.Measurement(exp, station)
    
    independents = [parameter, sweep_param]
    meas.register_parameter(parameter)
    meas.register_parameter(sweep_param, paramtype='array')
    meas.register_custom_parameter('amplitude', unit='V', setpoints=independents, 
                                   paramtype='array')
    meas.register_custom_parameter('phase', unit='rad', setpoints=independents,
                                   paramtype='array')
    
    with meas.run() as datasaver:
        for i, v in enumerate(values):
            setup_triggered_softsweep(controller, sweep_param, sweep_vals, integration_time,
                                      setup_awg=(i==0), verbose=(i==0), **kw)
            data = np.squeeze(controller.acquisition())[..., channel]

            result = []
            result.append((parameter, v))
            result.append((sweep_param, sweep_vals))
            result.append(('amplitude', np.abs(data)))
            result.append(('phase', np.angle(data)))
            datasaver.add_result(*result)
    
    return datasaver.dataset