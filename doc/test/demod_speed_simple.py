import numpy as np
import matplotlib as mpl
from matplotlib import pyplot as plt
import time


### dummy data generation
def dummy_data(nsamples, nrecords, nbuffers, sample_rate=1e9, 
               frq=20e6, dtype=np.uint16):
    
    tvals = np.arange(nsamples, dtype=np.float32) / sample_rate
    bb, rr, ss = np.meshgrid(
        np.ones(nbuffers),
        np.arange(nrecords) * (2*np.pi/nrecords),
        tvals,
        indexing='ij',
    )
    data = np.zeros((nbuffers, nrecords, nsamples, 2))
    data[..., 0] = 0.1 * bb * np.cos(2*np.pi*ss*frq + rr)
    data[..., 1] = 0.4 * np.sin(2*np.pi*ss*frq)
    data[:,:,:nsamples//4,0] = 0
    data[:,:,3*nsamples//4:,0] = 0
    data *= (2048 * 2)
    data += 2048
    data = data.astype(dtype)
    data <<= 4
    return tvals, data

def test_data_generation():
    frq = 20e6
    SR = 1e9
    period = int(SR/frq)
    
    tvals, data = dummy_data(10*128, 1, 1, SR, frq=frq)
    data.dtype = np.int16
    data -= 2048 * 16
    data = data / (16 * 4096)
    
    fig, axes = plt.subplots(2, 1, sharex=True, sharey=True)
    ax = axes[0]
    ax.plot(tvals * 1e6, (np.squeeze(data)[...,0]))
    ax = axes[1]
    ax.plot(tvals * 1e6, (np.squeeze(data)[...,1]))


### Acq controller test class
class CtlTest:
    
    def __init__(self, handler, nsamples, nrecords, nbuffers, 
                 sample_rate=1e9, data_dtype=np.uint16):
        
        self.tvals, self.data = dummy_data(nsamples, nrecords, nbuffers, sample_rate, frq, dtype=data_dtype)
        self.handler = handler
        self.handler.nbuffers = nbuffers
        self.handler.nrecords = nrecords
        self.handler.nsamples = nsamples
        self.handler.sample_rate = sample_rate
        
    def run(self):
        self.handler.pre_start_capture()
        for i in range(self.handler.nbuffers):
            self.handler.handle_buffer(self.data[i,...], i)
            
        self.data = self.handler.post_acquire()
            
        ht = np.mean(self.handler.handling_times)
        uht = np.std(self.handler.handling_times)
        norm_ht = 1e-3 * ht / ((self.handler.nsamples * self.handler.nrecords) / self.handler.sample_rate)
        mbps = (self.handler.nsamples * self.handler.nrecords * 2 * 2) / (1e-3 * ht) / (1024**2)
        
        return ht, uht, norm_ht, mbps
    

class BaseCtl:
    
    DATADTYPE = np.uint16
    number_of_channels = 2
    
    def __init__(self):
        self._average_buffers = False
        
    def data_shape(self):
        raise NotImplementedError
        
    def process_buffer(self, buf):
        raise NotImplementedError
    
    def pre_start_capture(self):
        self.tvals = np.arange(self.nsamples, dtype=np.float32) / self.nsamples
        self.buffer_shape = (self.nrecords,
                             self.nsamples,
                             self.number_of_channels)

        self.data = np.zeros(self.data_shape(), dtype=self.DATADTYPE)
        self.handling_times = np.zeros(self.nbuffers, dtype=np.float64)
    
        
    def handle_buffer(self, data, buffer_number=None):
        t0 = time.perf_counter()
        data.shape = self.buffer_shape
        
        if not buffer_number or self._average_buffers:
            self.data += self.process_buffer(data)
            self.handling_times[0] = (time.perf_counter() - t0) * 1e3
        else:
            self.data[buffer_number] = self.process_buffer(data)
            self.handling_times[buffer_number] = (time.perf_counter() - t0) * 1e3
    
class RawCtl(BaseCtl):

    def data_shape(self):
        shp = (self.nbuffers,
               self.nrecords,
               self.nsamples,
               self.number_of_channels)
        
        if not self._average_buffers:
            return shp
        else:
            return shp[1:]

    def process_buffer(self, buf):
        return buf
    
    def post_acquire(self):
        return (np.right_shift(self.data, 4).astype(np.float32) - 2048) / 4096
    

class AvgBufCtl(BaseCtl):
    
    DATADTYPE = np.uint32
    
    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)        
        self._average_buffers = True
    
    def data_shape(self):
        shp = (self.nrecords,
               self.nsamples,
               self.number_of_channels)
        return shp

    def process_buffer(self, buf):
        return buf
    
    def post_acquire(self):
        return (np.right_shift(self.data, 4).astype(np.float32) / self.nbuffers - 2048) / 4096
        
   
class AvgBufCtl2(BaseCtl):
    
    DATADTYPE = np.uint16
    
    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)        
        self._average_buffers = True
    
    def data_shape(self):
        shp = (self.nrecords,
               self.nsamples,
               self.number_of_channels)
        return shp

    def process_buffer(self, buf):
        return np.right_shift(buf, 4)
    
    def post_acquire(self):
        return self.data
    

### Script for test and benchmarking
rawctl = RawCtl()
avgctl = AvgBufCtl()
avgctl2 = AvgBufCtl2()


# test that we actually do the right operation
#test = CtlTest(avgctl, 10 * 128, 10, 10, 1e9)
#test.run()
#
#fig, axes = plt.subplots(2, 1, sharex=True, sharey=True)
#ax = axes[0]
#ax.plot(test.tvals * 1e6, (test.data[0,:,0]))
#ax = axes[1]
#ax.plot(test.tvals * 1e6, (test.data[0,:,1]))


# benchmark
nr_lst = np.arange(1, 1001, 25)
nht_lst = []
mbps_lst = []

for nr in nr_lst:
    test = CtlTest(avgctl, int(1000), int(nr), 1, 2e8, data_dtype=np.uint16)
    _, _, nht, mbps = test.run()
    nht_lst.append(nht)
    mbps_lst.append(mbps)

fig, axes = plt.subplots(2, 1, sharex=True)
ax = axes[0]
ax.plot(nr_lst, nht_lst, 'o')
ax.grid(dashes=[1,1])
ax.set_ylabel('norm. handling time', size='small')

ax = axes[1]
ax.plot(nr_lst, mbps_lst, 'o')
ax.grid(dashes=[1,1])
ax.set_ylabel('MB/s')
ax.set_xlabel('no of records')

plt.show()
