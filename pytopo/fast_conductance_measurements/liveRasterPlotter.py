from qcodes.plots.pyqtgraph import QtPlot

import numpy as np

import time

class liveRasterPlotter():

    def __init__(self, rasterer):
        self.rasterer = rasterer
        self.plots = {}

    def regenerate_plots(self):
        # kill old plots
        self.kill_plots()

        # and make new ones
        self.new_plots()

    def kill_plots(self):
        for k,v in self.plots.items():
            v['plot'].win.close()
        self.plots = {}

    def new_plots(self):
        # create new plots in a loop
        # for now only one plot per channel,
        # only for I quadrature
        for i, ch in enumerate(self.rasterer.MIDAS_channels()):
            plot_dict = {}

            # make data containers
            plot_dict['xvals'] = np.arange(0, self.rasterer.pixels_per_line())
            plot_dict['yvals'] = np.arange(0, self.rasterer.lines_per_acquisition())

            plot_dict['zvals'] = np.ones([self.rasterer.pixels_per_line(),
                                             self.rasterer.lines_per_acquisition()])
            plot_dict['zvals'][:,:] = np.NaN

            # create text for labels
            xlabel = 'AWG channel '+str(self.rasterer.AWG_channel())
            ylabel = 'MDAC channel '+str(self.rasterer.AWG_channel())
            plot_dict['name'] = 'MIDAS channel '+str(ch)

            # create empty plots
            plot_dict['plot'] = QtPlot(window_title=plot_dict['name'],
                        figsize=(450, 300),
                        fig_x_position=(i%4)*0.25,
                        fig_y_position=int(i/4)*0.33)

            plot_dict['plot'].subplots[0].setTitle(plot_dict['name'],
                            size='7pt',color='000000')

            # add data to plot            
            plot_dict['plot'].add(x=plot_dict['xvals'],
                                     y=plot_dict['yvals'],
                                     z=plot_dict['zvals'],
                                     xlabel=xlabel,
                                     xunit='arb. u.',
                                     ylabel=ylabel,
                                     yunit='arb. u.',
                                     zlabel=plot_dict['name'],
                                     zunit='arb. u.')

            self.plots[ch] = plot_dict

    def update_plots(self):
        for k, plot in self.plots.items():
            plot['plot'].update_plot()

    def prepare_instruments(self):
        self.rasterer.prepare_AWG()
        self.rasterer.AWG_channels_on()
        self.rasterer.AWG.start()
        self.rasterer.prepare_MIDAS()

    def measure(self):
        data = self.rasterer.arm_acquire_reshape()

        for d, ch in zip(data, self.rasterer.MIDAS_channels()):
            self.plots[ch]['zvals'][:,:] = np.real(d[:,:])

        self.update_plots()










