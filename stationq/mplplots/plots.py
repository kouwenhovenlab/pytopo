import numpy as np
from matplotlib import cm, colors
from .tools import pcolorgrid, get_color_cycle

# constants
default_cmap = cm.viridis


# tools for prettier plotting
def pplot(ax, x, y, yerr=None, linex=None, liney=None, color='r', fmt='o',
          alpha=0.5, mew=0.5, **kw):

    zorder = kw.pop('zorder', 0)
    line_dashes = kw.pop('line_dashes', [])
    line_lw = kw.pop('line_lw', 2)
    line_alpha = kw.pop('line_alpha', 0.5)
    line_color = kw.pop('line_color', color)
    line_zorder = kw.pop('line_zorder', -1)
    line_from_ypts = kw.pop('line_from_ypts', False)
    elinewidth = kw.pop('elinewidth', 0.5)
    label = kw.pop('label', None)
    label_x = kw.pop('label_x', x[-1])
    label_y_ofs = kw.pop('label_y_ofs', 0)
    label_kw = kw.pop('label_kw', {})
    fill_color = kw.pop('fill_color', 'same')

    syms = []

    if linex is None:
        linex = x

    if type(liney) == str:
        if liney == 'data':
            liney = y

    if yerr is not None:
        err = ax.errorbar(x, y, yerr=yerr, fmt='none', ecolor=color, capsize=0,
                          elinewidth=elinewidth, zorder=zorder)
        syms.append(err)

    if liney is None and line_from_ypts:
        liney = y.copy()

    if liney is not None:
        line, = ax.plot(linex, liney, dashes=line_dashes, lw=line_lw,
                        color=line_color, zorder=line_zorder, alpha=line_alpha)
        syms.append(line)
    if fill_color == 'same':
        fill_color = color
    fill, = ax.plot(x, y, fmt, mec='none', mfc=fill_color, alpha=alpha,
                    zorder=zorder, **kw)
    edge, = ax.plot(x, y, fmt, mec=color, mfc='None', mew=mew,
                    zorder=zorder, **kw)
    syms.append(fill)
    syms.append(edge)

    if label is not None:
        label_idx = np.argmin(np.abs(x - label_x))
        ax.annotate(label, (label_x, y[label_idx] + label_y_ofs),
                    color=color, **label_kw)

    return tuple(syms)


def ppcolormesh(ax, x, y, z, cmap=default_cmap, make_grid=True, **kw):
    if make_grid:
        _x, _y = pcolorgrid(x, y)
    else:
        _x, _y = x, y

    im = ax.pcolormesh(_x, _y, z, cmap=cmap, **kw)
    ax.set_xlim(_x.min(), _x.max())
    ax.set_ylim(_y.min(), _y.max())

    return im


def waterfall(ax, xs, ys, offset=None, style='pplot', **kw):
    cmap = kw.pop('cmap', default_cmap)
    linex = kw.pop('linex', xs)
    liney = kw.pop('liney', None)
    draw_baselines = kw.pop('draw_baselines', False)
    baseline_kwargs = kw.pop('baseline_kwargs', {})

    ntraces = ys.shape[0]
    if offset is None:
        offset = ys.max() - ys.min()

    if 'color' not in kw:
        colorseq = get_color_cycle(ntraces, colormap=cmap)
    else:
        c = kw.pop('color', None)
        colorseq = [c for n in range(ntraces)]

    for iy, yvals in enumerate(ys):
        x = xs if len(xs.shape) == 1 else xs[iy]
        y = yvals + iy * offset
        lx = linex if len(linex.shape) == 1 else linex[iy]
        ly = None if liney is None else liney[iy] + iy * offset
        color = colorseq[iy]

        if draw_baselines:
            baseline_opts = dict(color=color, lw=1, dashes=[1, 1])
            for k, v in baseline_kwargs:
                baseline_opts[k] = v
            ax.axhline(iy * offset, **baseline_opts)

        if style == 'pplot':
            pplot(ax, x, y, linex=lx, liney=ly, color=color, **kw)
        elif style == 'lines':
            ax.plot(x, y, '-', color=color, **kw)

