from qcodes.plots.pyqtgraph import QtPlot
from qcodes.instrument.base import Instrument

import ipywidgets as ipw

import numpy as np

import time

class liveRasterPlotter():

    def __init__(self, rasterer, *args, **kwargs):
        super().__init__(*args, **kwargs)

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

            plot_dict['zvals'] = np.ones([self.rasterer.lines_per_acquisition(),
                                self.rasterer.pixels_per_line()])
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

############### plotter with GUI ###############

class liveRasterPlotter_GUI(liveRasterPlotter, Instrument):
    '''
    How to use:
        - Create a MidasMdacAwg2DRasterer.
        - initialize liveRasterPlotter_GUI
        - at the end of the cell call
            > liverasterGUI.create_control_panel()
            without an assignment
        - "Prepare" prepares all instruments. Check point 8 in
            "How to use" of the MidasMdacAwg2DRasterer to see when
            you need to prepare instruments
        - New windows reopens preview windows. Do this when changing
            resolution or adding/removing measured MIDAS channels.

    TODO:
        - saving the measured data
        - selecting I/Q/amplitude/phase
    '''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def create_control_panel(self):

        ####################### AWG widgets #######################

        self.AWG_channel_select = ipw.BoundedIntText(
                        value=self.rasterer.AWG_channel(),
                        min=1, max=4,
                        step=1,
                        description='Chan:',
                        continuous_update=False)
        self.AWG_channel_select.observe(
                        lambda change: self.rasterer.AWG_channel(change['new']),
                        'value')

        self.AWG_Vpp_select = ipw.BoundedFloatText(
                        value=self.rasterer.AWG_Vpp(),
                        min=1e-3, max=1e-1,
                        step=1e-3,
                        description='Vpp (V):',
                        continuous_update=False)
        self.AWG_Vpp_select.observe(
                        self.set_AWG_Vpp,
                        'value')

        self.AWG_divider_select = ipw.BoundedFloatText(
                        value=1,
                        min=1, max=20,
                        step=0.1,
                        description='Divider:',
                        continuous_update=False)
        self.AWG_divider_select.observe(
                        self.set_AWG_Vpp,
                        'value')

        self.AWG_resolution_select = ipw.Dropdown(
                        options=[16,32,64,128],
                        value=self.rasterer.pixels_per_line(),
                        description='Resolution:')
        self.AWG_resolution_select.observe(
                        lambda change: self.rasterer.pixels_per_line(change['new']),
                        'value')

        AWG_layout = ipw.VBox([self.AWG_channel_select,
                            self.AWG_Vpp_select,
                            self.AWG_resolution_select,
                            self.AWG_divider_select])

        ####################### MDAC widgets #######################

        self.MDAC_channel_select = ipw.BoundedIntText(
                        value=self.rasterer.MDAC_channel(),
                        min=1, max=64,
                        step=1,
                        description='Chan:',
                        continuous_update=False)
        self.MDAC_channel_select.observe(
                        lambda change: self.rasterer.MDAC_channel(change['new']),
                        'value')

        self.MDAC_Vpp_select = ipw.BoundedFloatText(
                        value=self.rasterer.MDAC_Vpp(),
                        min=1e-3, max=1,
                        step=1e-3,
                        description='Vpp (V):',
                        continuous_update=False)
        self.MDAC_Vpp_select.observe(
                        lambda change: self.rasterer.MDAC_Vpp(change['new']),
                        'value')

        self.MDAC_resolution_select = ipw.Dropdown(
                        options=[16,32,64,128],
                        value=self.rasterer.lines_per_acquisition(),
                        description='Resolution:')
        self.MDAC_resolution_select.observe(
                        lambda change: self.rasterer.lines_per_acquisition(change['new']),
                        'value')

        MDAC_layout = ipw.VBox([self.MDAC_channel_select,
                            self.MDAC_Vpp_select,
                            self.MDAC_resolution_select])

        ####################### MIDAS widgets #######################

        self.averaging_select = ipw.Dropdown(
                        options=[16,32,64,128,256,512,1024,2048],
                        value=64,
                        description='Avg:')
        self.averaging_select.observe(
                        lambda change: self.rasterer.samples_per_pixel(change['new']),
                        'value')

        self.MIDAS_trigger_delay_select = ipw.BoundedIntText(
                        value=self.rasterer.MIDAS.trigger_delay(),
                        min=0, max=18e3,
                        step=1,
                        description='Trig. delay:',
                        continuous_update=False)
        self.MIDAS_trigger_delay_select.observe(
                        lambda change: self.rasterer.MIDAS.trigger_delay(change['new']),
                        'value')

        self.MIDAS_channel_selectors = []
        for i in range(1,8):
            checkbox = ipw.Checkbox(
                        value=(i==1),
                        description='Ch '+str(i),
                        continuous_update=False)
            checkbox.observe(
                        self.set_MIDAS_channels,
                        'value')
            self.MIDAS_channel_selectors.append(checkbox)


        MIDAS_channel_box = ipw.GridBox(self.MIDAS_channel_selectors,
                        layout=ipw.Layout(grid_template_columns="repeat(2, 90px)"))

        MIDAS_layout = ipw.VBox([self.averaging_select,
                            self.MIDAS_trigger_delay_select,
                            MIDAS_channel_box])

        ####################### Buttons #######################

        self.prepare_button = ipw.Button(
                            description='Prepare')
        self.prepare_button.on_click(lambda c: self.prepare_instruments())

        self.regenerate_plot_button = ipw.Button(
                            description='New windows')
        self.regenerate_plot_button.on_click(lambda c: self.regenerate_plots())

        self.measure_button = ipw.Button(
                            description='Measure')
        self.measure_button.on_click(lambda c: self.measure())

        self.notification_area = ipw.Label(
                            value='')

        main_button_layout = ipw.VBox([self.prepare_button,
                            self.regenerate_plot_button,
                            self.measure_button,
                            self.notification_area])

        ####################### Combine layouts #######################

        main_tab_widget = ipw.Tab()
        main_tab_layouts = [AWG_layout,
                            MDAC_layout,
                            MIDAS_layout]
        main_tab_titles = ['AWG',
                            'MDAC',
                            'MIDAS']
        main_tab_widget.children = main_tab_layouts
        for i, ttl in enumerate(main_tab_titles):
            main_tab_widget.set_title(i, ttl)

        Main_layout = ipw.HBox([main_button_layout, main_tab_widget])

        return Main_layout

    def set_AWG_Vpp(self, change):
        Vpp = self.AWG_Vpp_select.value
        divider = self.AWG_divider_select.value
        self.rasterer.AWG_Vpp(Vpp*divider)

    def set_MIDAS_channels(self, change):
        channels = []
        for i, checkbox in enumerate(self.MIDAS_channel_selectors):
            if checkbox.value:
                channels.append(i+1)
        self.rasterer.MIDAS_channels(channels)

    def measure(self):
        t_start = time.time()
        try:
            super().measure()
        except Exception as e:
            self.notification_area.value = str(e)
            raise
        t_stop = time.time()
        t_meas = np.round(t_stop-t_start,2)
        self.notification_area.value = 'Msmt time: '+str(t_meas)+' s'













