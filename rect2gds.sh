#!/bin/bash

./rect2lef.py -Tsky130 $1.rect $1.lef layermap.txt
strm2gds -d 20 --lefdef-map layermap.txt $1.lef $1.gds
