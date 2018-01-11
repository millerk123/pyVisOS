#!/usr/bin/env python

"""osh5def.py: Define the OSIRIS HDF5 data class and basic functions.
    The basic idea is to make the data unit and axes consistent with the data itself. Therefore users should only modify
    the unit and axes by modifying the data or by dedicated functions (unit conversion for example).
"""

import numpy as np
import re
import copy

# Important: the first occurrence of serial numbers between '-' and '.' must be the time stamp information
fn_rule = re.compile(r'-(\d+).')


class H5Data(np.ndarray):

    def __new__(cls, input_array, timestamp=None, name=None, data_attrs=None, run_attrs=None, axes=None):
        """wrap input_array into our class, and we don't copy the data!"""
        obj = np.asarray(input_array).view(cls)
        if timestamp:
            obj.timestamp = timestamp
        if name:
            obj.name = name
        if data_attrs:
            obj.data_attrs = data_attrs  # there is OSUnits obj inside
        if run_attrs:
            obj.run_attrs = run_attrs
        if axes:
            obj.axes = axes   # the elements are numpy arrays
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        self.timestamp = getattr(obj, 'timestamp', '0' * 6)
        self.name = getattr(obj, 'name', 'data')
        self.data_attrs = copy.deepcopy(getattr(obj, 'data_attrs', {}))
        self.run_attrs = getattr(obj, 'run_attrs', {})
        self.axes = copy.deepcopy(getattr(obj, 'axes', []))

    # need the following two function for mpi4py high level function to work correctly
    def __setstate__(self, state):
        self.__dict__ = state[-1]
        super(H5Data, self).__setstate__(state[:-1])

    # It looks like mpi4py/ndarray use reduce for pickling. One would think setstate/getstate pair should also work but
    # it turns out the __getstate__() function is never called!
    # Luckily ndarray doesn't use __dict__ so we can pack everything in it.
    def __reduce__(self):
        ps = super(H5Data, self).__reduce__()
        ms = ps[2] + (self.__dict__,)
        return ps[0], ps[1], ms

    def __getstate__(self):
        return self.__reduce__()

    def __str__(self):
        return ''.join([self.name, '-', self.timestamp])

    def __repr__(self):
        return ''.join([str(self.__class__), ' [', self.__str__(), ': ', str(self.shape), ']'])

    def __mul__(self, other):
        v = super(H5Data, self).__mul__(other)
        if isinstance(other, H5Data):
            v.data_attrs['UNITS'] = self.data_attrs['UNITS'] * other.data_attrs['UNITS']
        return v

    def __truediv__(self, other):
        v = super(H5Data, self).__truediv__(other)
        if isinstance(other, H5Data):
            v.data_attrs['UNITS'] = self.data_attrs['UNITS'] / other.data_attrs['UNITS']
        return v

    def __imul__(self, other):
        if isinstance(other, H5Data):
            self.data_attrs['UNITS'] = self.data_attrs['UNITS'] * other.data_attrs['UNITS']
        return self

    def __itruediv__(self, other):
        if isinstance(other, H5Data):
            self.data_attrs['UNITS'] = self.data_attrs['UNITS'] / other.data_attrs['UNITS']
        return self

    def __getitem__(self, index):
        """I am inclined to support only basic indexing/slicing. Otherwise it is too difficult to define the axes.
             However we would return an ndarray if advace indexing is invoked as it might help things floating...
        """
        v = super(H5Data, self).__getitem__(index)
        # if v.base is not self:  # not a view  # # we would never return at this point, right?
        #     return v
        # # v.axes = copy.deepcopy(self.axes)
        # # # # let's say a.shape=(4,4), a[1:3] **= 2 won't make sense any way ...
        # # # v.data_attrs['UNITS'] = copy.deepcopy(self.data_attrs['UNITS'])
        # #
        # # put everything into a list
        try:
            iter(index)
            idxl = index
        except TypeError:
            idxl = [index]
        try:
            pn, i, stop = 0, 0, len(idxl)
            while i < stop:
                if isinstance(idxl[i], int):  # i is a trivial dimension now
                    del v.axes[i - pn]
                    pn += 1
                elif isinstance(idxl[i], slice):  # also slice the axis
                    v.axes[i] = copy.deepcopy(v.axes[i])  # numpy array deepcopy
                    v.axes[i].ax = v.axes[i].ax[idxl[i]]
                elif idxl[i] is Ellipsis:  # let's jump out and count backward
                    i += self.ndim - stop
                elif idxl[i] is None:
                    pass
                else:  # type not supported
                    return v.view(np.ndarray)
                i += 1
        except AttributeError:  #TODO(1) .axes was lost for some reason, need a better look
            pass
        return v

    def meta2dict(self):
        """return a deep copy of the meta data as a dictionary"""
        return copy.deepcopy(self.__dict__)

    def transpose(self, *axes):
        v = super(H5Data, self).transpose(*axes)
        if not axes:  # axes is none, numpy default is to reverse the order
            axes = range(len(v.axes)-1, -1, -1)
        v.axes = [self.axes[i] for i in axes]
        return v

    def sum(self, axis=None, out=None, dtype=None, **unused_kw):
        dim = self.ndim
        o = super(H5Data, self).sum(axis=axis, out=out)
        if out is not None:
            out = o.asdtype(dtpye) if dtype else o.asdtye(out.dtype)
        if axis is None:  # default is to sum over all axis, return a value
            return o[0]
        if isinstance(axis, int):
            del o.axes[axis]
        else:
            # remember axis index can be negative
            o.axes = [v for i, v in enumerate(o.axes) if i not in axis and i-dim not in axis]
        return o

    def __array_wrap__(self, out, context=None):
        """Here we handle the unit attribute
        We do not check the legitimacy of ufunc operating on certain unit. We hard code a few unit changing
        rules according to what ufunc is called
        For now we only support powers, numpy.multiply/numpy.divide etc are not implemented
        """
        # the document says that __array_wrap__ could be deprecated in the future but this is the most direct way...
        __ufunc_mapping = {'sqrt': '1/2', 'cbrt': '1/3', 'square': '2', 'power': 0}
        op = __ufunc_mapping.get(context[0].__name__)
        if op is not None:
            if not op:  # op is 'power', get the second operand
                op = context[1][1]
            try:
                out.data_attrs['UNITS'] **= op
            except KeyError:  # no units defined, return silently
                pass
        return np.ndarray.__array_wrap__(self, out, context)
