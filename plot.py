import gpw
import math
import random
import re
import string
import sys

PY3 = (sys.version_info.major == 3)

alnum = string.letters + string.digits
def escape(s):
    out = ''
    for c in s:
        if c in '\\\'@_':
            out += '\\'
        if c in alnum + ' _@\\:/-."\'()':
            out += c
        else:
            out += ' '
    return out

def plot(title, xlabel, ylabel, xtics, data, width=1024, height=768, bare=False):
    title, xlabel, ylabel = map(escape, (title, xlabel, ylabel))
    xtics = ', '.join(['"{}" {:d}'.format(escape(c), i) for i, c in enumerate(xtics)])

    # this data must be well-formed
    keys = sorted(data.keys())
    colwise = [[data[k][i] for k in keys] for i in xrange(len(data[keys[0]]))]
    ymax = math.ceil(max([max(d) for d in data.values()]))
    ntics = 10

    yunit = ''
    match = re.match(r'^(.*)\((.+)\)$', ylabel)
    if match:
        ylabel, yunit = match.groups()

    # might want svg
    plotscript = '''
    set terminal pngcairo transparent enhanced size {width:d},{height:d}

    set title '{title}'
    set xlabel '{xlabel}'
    set ylabel '{ylabel}'
    set key outside
    set format y '%g{yunit}'
    set yrange [0:]
    set grid
    set tics scale 0
    set xtics nomirror rotate 90 font ", 8" ({xtics})
    '''.format(**locals())

    if bare:
        plotscript += '''
        set title '{title}' font ", 10" offset 0,-0.8
        unset xlabel
        unset ylabel
        unset xtics
        unset ytics
        unset key

        set bmargin 0.5
        set lmargin 0.5
        set rmargin 0.5
        set tmargin 1
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
