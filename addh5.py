import numpy as np
import sys, glob, os
import osh5io
import osh5def
import osh5vis
import osh5utils

def main():
    args = sys.argv
    files = {}
    for a in args[1:-1]:
        if a[-1] != '/':
            a1 = a + '/'
        else:
            a1 = a
        files[a] = sorted(glob.iglob(a1 + '*.h5'))

    save_dir = args[-1]
    if save_dir[-1] != '/':
        save_dir = save_dir + '/'
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    for i,f in enumerate(files[args[1]]):
        i1 = f.rfind('/') + 1
        i2 = f.rfind('-') + 1
        name = 'sum-' + f[i1:i2]
        dat = osh5io.read_h5(f)
        for j in xrange(len(args)-3):
            g = files[args[j+2]][i]
            add = osh5io.read_h5(g)
            dat = dat + add
            i1 = g.rfind('/') + 1
            i2 = g.rfind('-') + 1
            name = name + g[i1:i2]
        name = name + g[i2:]
        osh5io.write_h5(dat,filename=save_dir + name)
        print name


if __name__ == "__main__":
    main()