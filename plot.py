import gpw
import math
import random
import string
import sys

PY3 = (sys.version_info.major == 3)

alnum = string.letters + string.digits
def escape(s):
    out = ''
    for c in s:
        if c in '\\\'@_':
            out += '\\'
        if c in alnum + ' _@\\:/-."\'':
            out += c
        else:
            out += ' '
    return out

def plot(title, xlabel, ylabel, xtics, data, width=1024, height=768):
    title, xlabel, ylabel = map(escape, (title, xlabel, ylabel))
    xtics = ', '.join(['"{}" {:d}'.format(escape(c), i) for i, c in enumerate(xtics)])

    # this data must be well-formed
    keys = sorted(data.keys())
    colwise = [[data[k][i] for k in keys] for i in xrange(len(data[keys[0]]))]
    ymax = math.ceil(max([max(d) for d in data.values()]))
    ntics = 10

    # might want svg
    plotscript = '''
    set terminal png size {width:d},{height:d}

    set title '{title}'
    set xlabel '{xlabel}'
    set ylabel '{ylabel}'
    set key outside
    set yrange [0:]
    set grid
    set tics scale 0
    set xtics nomirror rotate 90 font ", 8" ({xtics})
    '''.format(**locals())

    plotscript += 'plot ' + ', '.join([
        '''"gpw_DATAFILE_gpw" using {:d} title '{}' with lines'''.format(i + 1, escape(title))
        for i, title in enumerate(keys)
    ])

    plotdata = '\n'.join([
        ' '.join(['{:f}'.format(n) for n in row])
        for row in colwise
    ]) + '\n'

    if PY3:
        plotscript = plotscript.encode()
    plotout = gpw.plot(plotdata, plotscript=plotscript, usefifo=False)
    return plotout
