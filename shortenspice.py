#!/usr/bin/python3

import sys
import re
import datetime
import os

ckts = dict()
ids = dict()

if len(sys.argv) <= 1:
	print("shortenspice.py <file>")
	print("Prints the spice file, removing the template parameters from each subcircuit in favor of a unique id. This is useful for shortening subcircuit names for HSIM.")
else:
	with open(sys.argv[1], 'r') as fptr:
		for line in fptr:
			line = line.split()
			if line and line[0] == '.subckt':
				ms = re.finditer(r'[a-zA-Z]', line[1])
				if ms:
					m = None
					for m in ms:
						pass
					idx = m.span()[-1]
					if idx < len(line[1]):
						name = line[1][0:idx]
						if name in ids:
							ids[name] += 1
						else:
							ids[name] = 0
						name += '_' + str(ids[name])
						ckts[line[1]] = name
						line[1] = name
			elif line and line[0].startswith("x"):
				i = 0
				while i < len(line) and '=' in line[-1-i]:
					i += 1
				if i < len(line):
					if line[-1-i] in ckts:
						line[-1-i] = ckts[line[-1-i]]
			print(' '.join(line))
