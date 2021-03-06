import numpy as np
import scipy.signal as signal
import numpy.fft as fft
WMAT_CACHE = {}


def linear_filter_matrix(nf, df, patch_c, patch_w, filter_factor, zero_flags,
flags, cache = WMAT_CACHE, discrete_ft = False):
    '''
    Args:
        nf, number of frequencies.
        df, difference between channels.
        flags, numpy bool (or int) array of flags
        filter_factor, float, factor by which to suppress modes specified in patch_c and patch_w
        patch_c,  a list of window centers for delay values (floats) to filter.
        patch_w,  a list of window widths for delay values (floats) to filter.
        zero_flags, bool, if true, set values in flagged frequency channels to zero, even if not filtering.
        cache, optional dictionary to store precomputed filter matrices. Default, use dictionary in this namespace.
        discrete_ft, if True, generate matrix using discrete fourier transform from a diagonal in delay.
    Returns:
        weight matrix (nfreq, nfreq) -- a linear filter matrix that removes structures
    '''
    freqs = np.arange(-nf/2,nf/2) * df
    wkey = (nf,freqs[1]-freqs[0],filter_factor,zero_flags,discrete_ft)+tuple(np.where(flags)[0])\
    + tuple(patch_c) + tuple(patch_w)
    if not wkey in WMAT_CACHE:
        if not discrete_ft:
            fx,fy=np.meshgrid(freqs,freqs)
            filter_mat_inv = np.zeros((nf,nf),dtype=complex)
            for cp,cw in zip(patch_c, patch_w):
                if filter_factor > 0.:
                    filter_mat_inv += np.sinc(2.*(fx-fy) * patch_w).astype(complex) * np.exp(-2j*np.pi*(fx-fy) * patch_c) / filter_factor
            filter_mat_inv = filter_mat_inv + np.identity(len(freqs))
        else:
            delays = fft.fftshift(fft.fftfreq(nf,df))
            fmat_diag = np.ones(nf,dtype=complex) * filter_factor
            for cp,cw in zip(patch_c,patch_w):
                fmat_diag[np.abs(delays-cp)<=cw] += (1./2./cw)
            filter_mat_inv = np.diag(fmat_diag)
            #generate discrete FT matrix.
            imag,jmat = np.meshgrid(np.arange(-nf/2,nf/2),np.arange(-nf/2,nf/2))
            ftmat = np.exp(2j * np.pi * imat * jmat / nf)
            filter_mat_inv = np.dot(ftmat, np.dot(filter_mat_inv, np.conj(ftmat.T)))
        if zero_flags:
            filter_mat_inv[:,flags]=0.
            filter_mat_inv[flags,:]=0.

        filter_mat = np.linalg.pinv(filter_mat_inv)
        WMAT_CACHE[wkey]=filter_mat

    return WMAT_CACHE[wkey]


def dedekind(freqs,ydata,flags,filter_factor = 1e-6,patch_c = [0.], patch_w = [100e-9],weights = "WTL",
             zero_flags=True,output_domain='delay',taper='boxcar', cache = WMAT_CACHE):
    '''
    a linear delay filter that suppresses modes within rectangular windows in delay space listed in list "patch_c"
    by a factor of "filter_factor"
    Args:
        freqs, numpy float array of frequency values
        flags, numpy bool (or int) array of flags
        filter_factor, float, factor by which to suppress modes specified in patch_c and patch_w
        patch_c,  a list of window centers for delay values (floats) to filter.
        patch_w,  a list of window widths for delay values (floats) to filter.
        weights, string, use "WTL" to filter regions specified in patch_c and patch_w or "I" to do not filtering (just a straight fft)
        renormalize, EXPERIMENTAL bool, try to restore filtered regions after FT.
        zero_flags, bool, if true, set values in flagged frequency channels to zero, even if not filtering.
        output_domain, string, specify "frequency" or "delay"
        taper, string, specify the multiplicative tapering function to apply before filtering.
        cache, optional dictionary to store precomputed filter matrices. Default, use dictionary in this namespace.
    Returns:
        if output_domain == 'delay',
            returns delays, output where output is the filtered delay transformed data set.
        if output_domain == 'frequency'
            returns frequencies, output where output is the filtered frequency domain data set.
    Example:
        linear_filter(x, y, f, 1e-6, patch_c = [0.], patch_w = 100e-9) will filter out modes (including flagged sidelobes) within a window
        centered at delay = 0. ns with width of 200 ns (region between -100 and 100 ns).
    '''
    nf = len(freqs)
    taper=signal.windows.get_window(taper,nf)
    taper/=np.sqrt((taper*taper).mean())
    taper_mat = np.diag(taper)
    if weights=='I':
        wmat = np.identity(nf)
        if zero_flags:
            wmat[:,flags]=0.
            wmat[flags,:]=0.
    elif weights == 'WTL':
        wmat = linear_filter_matrix(nf = len(freqs), df = freqs[1]-freqs[0], patch_c = patch_c, patch_w = patch_w,
                                    filter_factor = filter_factor, zero_flags = zero_flags, flags = flags, cache = cache)
    output = ydata
    output = np.dot(wmat,output)
    output = fft.fft(output * taper)
    #if renormalize:
    #    igrid,jgrid = np.meshgrid(np.arange(-nf/2,nf/2),np.arange(-nf/2,nf/2))
    #    fftmat = np.exp(-2j*np.pi*igrid*jgrid/nf)
        #fftmat[flags,:]=0.
        #fftmat[:,flags]=0.
    #    mmat = np.dot(fftmat,np.dot(wmat,np.conj(fftmat).T))
        #print(np.linalg.cond(mmat))
    #    mmat_inv = np.linalg.pinv(mmat)
    #else:
    #    mmat_inv = np.identity(nf)
    #output=np.dot(mmat_inv,output)

    if output_domain=='frequency':
        output = fft.ifft(output)/taper
        x = freqs
    else:
        x = np.arange(-nf/2,nf/2)/((freqs[1]-freqs[0]) * nf)
        output = fft.fftshift(output)
    #print(output.shape)
    return x,output
