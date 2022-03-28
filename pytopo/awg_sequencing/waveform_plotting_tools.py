import broadbean as bb
import matplotlib.pyplot as plt
import numpy as np

def draw_element(el, channel_x=1, channel_y=2,
                    x_offset=0, y_offset=0,
                    lw=2, ms=20, skip_samples=20):
    seq = bb.Sequence()
    seq.addElement(1, el)
    seq.setSR(el._meta['SR'])

    forged_seq = seq.forge(includetime=True, apply_filters=False)

    wfm_x = forged_seq[1]['content'][1]['data'][channel_x]['wfm']
    wfm_y = forged_seq[1]['content'][1]['data'][channel_y]['wfm']

    wx = np.append(wfm_x[-1], wfm_x)+x_offset
    wy = np.append(wfm_y[-1], wfm_y)+y_offset

    plt.plot(wx,wy, 'k', lw=lw)
    plt.plot(wx,wy, 'w', lw=lw/2)
    
    plt.scatter(wx[::skip_samples],wy[::skip_samples],c=range(len(wx[::skip_samples])), marker='.', s=ms, cmap='rainbow')
