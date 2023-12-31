#!/bin/bash

for FILE in $(find . -name '*.l'); do
	echo "$FILE"
	/home/nbingham/workspace/broccoli/scripts/hspice2xyce $FILE > tmp
	yes | mv tmp $FILE
done

for FILE in $(find . -name '*.inc'); do
	echo "$FILE"
	/home/nbingham/workspace/broccoli/scripts/hspice2xyce $FILE > tmp
	yes | mv tmp $FILE
done

for FILE in $(find . -name '*.lib'); do
	echo "$FILE"
	/home/nbingham/workspace/broccoli/scripts/hspice2xyce $FILE > tmp
	yes | mv tmp $FILE
done

for FILE in $(find . -name '*.spice'); do
	echo "$FILE"
	/home/nbingham/workspace/broccoli/scripts/hspice2xyce $FILE > tmp
	yes | mv tmp $FILE
done
