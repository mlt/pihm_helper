#!/usr/bin/env python
# -*- coding: utf-8; mode: python; mode: ropemacs -*-
# http://packages.python.org/an_example_pypi_project/sphinx.html

""" This module extracts common NLDAS-2 data using OPenDAP.

.. moduleauthor:: Mikhail Titov <mlt@gmx.us>

The main workhorse is :func:`extract`. Create an instance of Extractor, set coverage and other members.
Coverage is a tuple of extent and tuple of cells (tuple of NLDAS_ID, NLDAS_X, NLDAS_Y).
That tuple can be obtained from coverage using :func:`setCoverage` if all features of a
shapefile shall be used.

Synopsis::

    e = Extractor()
    e.begin = e.end = some date
    e.output = dir
    e.setCOverage(filename)
    e.extract()

"""

from __future__ import print_function
import os
try:
    from osgeo import ogr
except ImportError:
    import ogr
try:                            # pydap 2.x
    from dap.client import open as open_url
    from dap.lib import CACHE
except ImportError:             # pydap 3.x
    from pydap.client import open_url
    from pydap.lib import CACHE
from dateutil.parser import parse
from dateutil.tz import tzutc
from datetime import datetime
from numpy import linspace, column_stack, savetxt, squeeze, asarray, vectorize, dtype, str_
import logging

log = logging.getLogger(__name__)

utcfromtimestamp_vec = vectorize(datetime.utcfromtimestamp)

# def d2str(d):
#     t = datetime.utcfromtimestamp((d - EPOCH_OFFSET_DAYS) * 86400.)
#     return t.isoformat()

# d2str_vec = vectorize(d2str, [((str_, 10))])
# d2str_vec = vectorize(d2str, dtype('|S10'))

# __all__ = ['coverage', 'fetch_data', 'VARIABLES']

URL = 'http://hydro1.sci.gsfc.nasa.gov/dods/NLDAS_FORA0125_H.002'
# Python datetime ordinal counts 1 jan 0001 as Gregorian day 1
# whereas NLDAS-2 references from it (Rata Die), i.e. 24 hours offset to day 0
# 13z01jan1979 = ds.time[0] => 722451.54166667
# 722451.54166667 * 24 = 17338837
# To get MS Excel's serial we can subtract 693595 from NLDAS-2 date
# See also: http://en.wikipedia.org/wiki/Rata_Die

BASE_HOUR = 17338813
EXCEL_OFFSET = 693595
EPOCH_OFFSET_DAYS = EXCEL_OFFSET + 25569
BASE_LAT8 = 199.504
BASE_LON8 = -1000.504

VARIABLES = {'apcpsfc'  : 'PP',
             'pevapsfc' : 'VP',
             'tmp2m'    : 'TT'}

CHUNK = 250                     # hours

class Extractor:
    def __init__(self):
        self.callback = None
        self.begin = None
        self.end = None
        self.output = "."
        self.csv = False
        self.want_quit = False  # shall be used in derived GUI class

    def setCoverage(self, input):
        """Extract coverage from a shapefile ``input``.

        :param input: file name with features
        :type input: str

        """
        if type(input) == str:
            dataSource = ogr.Open(input)
            if dataSource:
                layer = dataSource.GetLayer()
                defn = layer.GetLayerDefn()
                nldasid = defn.GetFieldIndex('NLDAS_ID')
                nldasx = defn.GetFieldIndex('NLDAS_X')
                nldasy = defn.GetFieldIndex('NLDAS_Y')
                if (any((x==-1 for x in (nldasid, nldasx, nldasy)))):
                    raise Exception("Layer must have NLDAS_ID, NLDAS_X, NLDAS_Y fields")
                ext = layer.GetExtent()
                out = []
                feature = layer.GetNextFeature()
                while feature:
                    x = feature.GetFieldAsInteger(nldasx)#'NLDAS_XXX')
                    y = feature.GetFieldAsInteger(nldasy)#'NLDAS_Y')
                    id = feature.GetFieldAsString(nldasid)#'NLDAS_ID')
                    out.append((id,x,y))
                    feature.Destroy()
                    feature = layer.GetNextFeature()
                self.coverage = (ext, out)
        else:
            self.coverage = input

# def inclusive_range(start, stop, step):
#     for x in xrange(start, stop-1, step):
#         yield x
#     yield stop

    def _write_csv_header(self):
        for feature in self.coverage[1]:
            id = feature[0]
            name = os.path.join(self.output, "{:s}.csv".format(id))
            with open(name, 'w') as f:
                print(*(["UTC"] + VARIABLES.keys()), sep=",", file=f)

    @staticmethod
    def date2index(d):
        return d.toordinal() * 24 + d.hour - BASE_HOUR

    def extract(self):
        """ Extract selected cells using OPeNDAP
        """
        lon_min, lon_max, lat_min, lat_max = self.coverage[0]
        xmin = int(lon_min*8 - BASE_LON8)
        xmax = int(lon_max*8 - BASE_LON8)
        ymin = int(lat_min*8 - BASE_LAT8)
        ymax = int(lat_max*8 - BASE_LAT8)
        begin = self.date2index(self.begin)
        if self.end:
            end = self.date2index(self.end)
        else:
            end = begin
        end += 1          # in case we want to slice begin:begin or alike
        str = "Slicing as if [{:d}:{:d}][{:d}:{:d}][{:d}:{:d}]".format(
            begin, end, ymin, ymax, xmin, xmax)
        log.debug(str)
        ds = open_url(URL)
        # print(ds.time[0])
        # return
        # time_range = inclusive_range(begin, end, 1000)
        time_range = range(begin, end-1, CHUNK) + [end]
        time_slices = [ slice(a, b) for a, b in zip(time_range[:-1], time_range[1:]) ]
        start = datetime.now()
        if self.csv:
            self._write_csv_header()
        for the_slice in time_slices:
            log.debug("Working on {:s}".format(the_slice))
            t = linspace((the_slice.start-begin)/24., (the_slice.stop-begin)/24., the_slice.stop-the_slice.start, False)
            t2 = t + 1./24 - 0.00001
            all = {}
            # enumerate()
            for var, code in VARIABLES.iteritems():
                if self.want_quit:
                    return
                if self.callback:
                    self.callback(var, the_slice.start-begin, end-begin)
                ref = ds[var]
                arr = ref[the_slice, ymin:ymax, xmin:xmax]
                # time_len = arr.shape[0]  # lat_len, lon_len
                for feature in self.coverage[1]:
                    id = feature[0]
                    x = feature[1] - 1 - xmin
                    y = feature[2] - 1 - ymin
                    v = arr[:, y, x]
                    str = "id={:s}, x={:d}, y={:d}, time={:s}, lon={:s}, lat={:s}".format(
                        id, x, y, v.data[1][:1] + v.data[1][-2:], v.data[2], v.data[3])
                    log.debug(str)
                    vv = squeeze(asarray(v.data[0]))
                    if self.csv:
                        if not id in all:
                            # all[id] = (squeeze(v.data[1]) - EXCEL_OFFSET,) # Excel's serial date
                            # requires numpy 1.7.0+
                            # all[id] = (utcfromtimestamp_vec((squeeze(v.data[1]) - EPOCH_OFFSET_DAYS) * 86400.),) # datetime
                            # all[id] = (d2str_vec(squeeze(v.data[1])),) # str
                            # all[id] = (d2str_vec(squeeze(v.data[1])).tolist(),) # str
                            # all[id]  = (v.data[1].tolist(),)
                            # +.1 to overcome rounding issues making it 1:59:59.999
                            all[id] = (utcfromtimestamp_vec((squeeze(v.data[1]) - EPOCH_OFFSET_DAYS) * 86400. + .1).tolist(),) # datetime
                        all[id] += (vv.tolist(),)
                    else:       # PIHM 3
                        name = os.path.join(self.output, "{:s}z{:s}.txt".format(id, code))
                        with open(name, 'a') as f:
                            out = column_stack((t, vv, t2, vv))
                            savetxt(f, out, '%.5f')
            if self.csv:
                for id, vars in all.iteritems():
                    name = os.path.join(self.output, "{:s}.csv".format(id))
                    with open(name, 'a') as f:
                        # savetxt(f, column_stack(vars), '%.5f', delimiter=',')
                        # savetxt(f, column_stack(vars), '%10.5s', delimiter=',')
                        for row in zip(*vars):
                            print("{:s},{:f},{:f},{:f}".format(
                                    row[0].strftime("%Y-%m-%d %H:%M:%S"), *row[1:]), file=f)
        td = datetime.now() - start
        s = "It took me {:s}".format(td)
        log.info(s)

def main():
    """ CLI interface to module.
    """
    import argparse

    # logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser(description='Extracts data from NLDAS-2 using OPeNDAP')
    parser.add_argument(nargs=1, dest='input',
                        help='Input file with selected reference polygons')
    parser.add_argument(nargs=1, dest='begin',
                        help='Starting date (whatever dateutil parser can recognize)')
    parser.add_argument(nargs='?', dest='end',
                        help='End date (whatever dateutil parser can recognize)')
    parser.add_argument('--output', dest='output',
                        default='.',
                        help='Output folder')
    parser.add_argument('--cache', dest='cache',
                        default='cache',
                        help='Cache folder')
    parser.add_argument('--csv', action='store_true',
                        help='Save in CSV format? (PIHM 3 otherwise)')
    args = parser.parse_args()

    CACHE = args.cache

    end = None
    if args.end:
        end = parse(args.end)
        end = end.astimezone(tzutc())

    begin = parse(args.begin[0])
    begin = begin.astimezone(tzutc())

    e = Extractor()
    e.setCoverage(args.input[0])
    e.begin = begin
    e.end = end
    e.output = args.output
    e.csv = args.csv
    e.extract()

if __name__ == '__main__':
    main()
