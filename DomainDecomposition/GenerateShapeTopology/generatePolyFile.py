#!/usr/bin/env python

from __future__ import print_function
try:
    from osgeo import ogr
    # from osgeo.gdal import VersionInfo as ogrVersion
    # print "Got osgeo"
except:
    import ogr
#     from gdal import VersionInfo as ogrVersion
#     print "Got plain ogr"
# print ogrVersion()
# import shapely
# from shapely.wkb import loads
# geom = loads(feature.GetGeometryRef().ExportToWkb())

def generatePolyFile(input, output):
    with open(output, 'w') as f:
        dataSource = ogr.Open(input)
        if dataSource:
            layer = dataSource.GetLayer()
            feature = layer.GetNextFeature()
            points = 0
            segments = 0
            while feature:
                geometry = feature.GetGeometryRef()
                pts = geometry.GetPointCount()
                points += pts
                segments += pts-1
                feature.Destroy()
                feature = layer.GetNextFeature()
            # we could have read into a temporary tuple instead of reading 3 times
            layer.ResetReading()
            print("{:d} 2 0 0".format(points), file=f)
            feature = layer.GetNextFeature()
            point = 1
            while feature:
                geometry = feature.GetGeometryRef()
                pts = geometry.GetPoints()
                for pt in pts:
                    print("{:d} {:f} {:f}".format(point, pt[0], pt[1]), file=f)
                    point += 1
                feature.Destroy()
                feature = layer.GetNextFeature()
            layer.ResetReading()
            print("{:d} 0".format(segments), file=f)
            feature = layer.GetNextFeature()
            segment = 1
            point = 1
            while feature:
                geometry = feature.GetGeometryRef()
                pts = geometry.GetPointCount()
                for pt in range(pts-1):
                    print("{:d} {:d} {:d}".format(segment, point, point+1), file=f)
                    segment += 1
                    point += 1
                point += 1
                feature.Destroy()
                feature = layer.GetNextFeature()
            print("0", file=f)

            dataSource.Destroy()

if __name__ == '__main__':
    import argparse, re

    parser = argparse.ArgumentParser(description='Convert polylines into a PSLG in a poly file for Triangle')
    parser.add_argument(nargs='?', dest='input',
                       default='MergeFeatures.shp',
                       help='Input file with polylines (> 2 vertices OK) [MergeFeatures.shp]')
    parser.add_argument(dest='output', nargs='?',
                       help='Output file for Triangle. If omitted, as input with .poly extension.')
    args = parser.parse_args()

    output = re.sub("\\..+$|$", ".poly", args.input)
    if args.output:
        output = args.output;
    generatePolyFile(args.input, output)
