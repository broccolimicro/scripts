#!/bin/bash

for FILE in $(find . -name '*.l'); do
	echo "$FILE"
	~/workspace/broccoli/pr/hspice2xyce $FILE > tmp
	mv tmp $FILE
done

for FILE in $(find . -name '*.spice'); do
	echo "$FILE"
	~/workspace/broccoli/pr/hspice2xyce $FILE > tmp
	mv tmp $FILE
done
