# -*- coding: utf-8 -*-
"""
 This script initializes the plugin, making it known to QGIS.
"""
def name():
  return "PIHM helper"
def description():
  return "Auxilary tools for PIHM"
def version():
  return "Version 0.1"
def qgisMinimumVersion():
  return "1.8"
def classFactory(iface):
  from Helper import Helper
  return Helper(iface)


def icon():
    """
    Icon
    """
    return "icon.png"
