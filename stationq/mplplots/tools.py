import numpy as np
from matplotlib import pyplot as plt
from matplotlib import gridspec, cm
from matplotlib.colors import rgb2hex


# color management tools
def get_color_cycle(n, colormap, start=0., stop=1., format='hex'):
    if type(colormap) == str:
        colormap = getattr(cm, colormap)

    pts = np.linspace(start, stop, n)
    if format == 'hex':
        colors = [rgb2hex(colormap(pt)) for pt in pts]
    return colors


# tools for color plots
def centers2edges(arr):
    e = (arr[1:] + arr[:-1]) / 2.
    e = np.concatenate(([arr[0] - (e[0] - arr[0])], e))
    e = np.concatenate((e, [arr[-1] + (arr[-1] - e[-1])]))
    return e


def pcolorgrid(xaxis, yaxis):
    xedges = centers2edges(xaxis)
    yedges = centers2edges(yaxis)
    xx, yy = np.meshgrid(xedges, yedges)
    return xx, yy


# creating and formatting figures
def get_fig(widths, heights, margins=0.5, dw=0.2, dh=0.2, make_axes=True):
    """
    Create a figure and grid where all dimensions are specified in inches.
    Arguments:
        widths: list of column widths
        heights: list of row heights
        margins: either a scalar or a list of four numbers (l, r, t, b)
        dw: white space between subplots, horizontal
        dh: white space between subplots, vertical
        make_axes: bool; if True, create axes on the grid and return,
                   else return the gridspec.
    """
    wsum = sum(widths)
    hsum = sum(heights)
    nrows = len(heights)
    ncols = len(widths)
    if type(margins) == list:
        l, r, t, b = margins
    else:
        l = r = t = b = margins

    figw = wsum + (ncols - 1) * dw + l + r
    figh = hsum + (nrows - 1) * dh + t + b

    # margins in fraction of the figure
    top = 1. - t / figh
    bottom = b / figh
    left = l / figw
    right = 1. - r / figw

    # subplot spacing in fraction of the subplot size
    wspace = dw / np.average(widths)
    hspace = dh / np.average(heights)

    fig = plt.figure(figsize=(figw, figh))
    gs = gridspec.GridSpec(nrows, ncols,
                           height_ratios=heights, width_ratios=widths)
    gs.update(top=top, bottom=bottom, left=left, right=right,
              wspace=wspace, hspace=hspace)

    if make_axes:
        axes = []
        for i in range(nrows):
            for j in range(ncols):
                axes.append(fig.add_subplot(gs[i, j]))

        return fig, axes

    else:
        return fig, gs


def format_default_ax(ax, top=False, right=False, xlog=False, ylog=False):
    ax.tick_params(axis='x', which='both', pad=2,
                   top='off' if not top else 'on',
                   labeltop='off' if not top else 'on',
                   bottom='on' if not top else 'off',
                   labelbottom='on' if not top else 'off', )
    if top:
        ax.xaxis.set_label_position('top')

    ax.tick_params(axis='y', which='both', pad=2,
                   right='off' if not right else 'on',
                   labelright='off' if not right else 'on',
                   left='on' if not right else 'off',
                   labelleft='on' if not right else 'off')
    if right:
        ax.yaxis.set_label_position('right')

    ax.xaxis.labelpad = 2
    ax.yaxis.labelpad = 2


def format_right_cax(cax):
    format_default_ax(cax, right=True)
    cax.tick_params(axis='x', top='off', bottom='off', labelbottom='off',
                    labeltop='off')
