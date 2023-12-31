#!/usr/bin/python3

import os
import sys

hasGDSTK = True
try:
	import gdstk
except ImportError:
	hasGDSTK = False

def stripComments(line):
	escape = False
	inString = False
	for i, c in enumerate(line):
		if not escape and (c == "\"" or c == "\'"):
			inString = not inString
		elif inString and c == "\\":
			escape = not escape
		elif not inString and c == "#":
			return line[0:i]
		else:
			escape = False
	return line

def loadActConf(path):
	result = dict()
	stack = [result]
	with open(path, "r") as fptr:
		for number, line in enumerate(fptr):
			if "#" in line:
				line = line[0:line.index("#")]
			args = [arg.strip() for arg in line.strip().split(" ")]
			if len(args) > 0:
				if args[0] == "include":
					result = result | loadActConf(args[1][1:-1])
				elif args[0] == "begin":
					stack[-1][args[1]] = dict()
					stack.append(stack[-1][args[1]])
				elif args[0] == "end":
					stack.pop()
				elif args[0] == "string":
					stack[-1][args[1]] = args[2][1:-1]
				elif args[0] == "int":
					stack[-1][args[1]] = int(args[2])
				elif args[0] == "real":
					stack[-1][args[1]] = float(args[2])
				elif args[0] == "int_table":
					stack[-1][args[1]] = [int(arg) for arg in args[2:]]
				elif args[0] == "string_table":
					stack[-1][args[1]] = [arg[1:-1] for arg in args[2:]]
	return result

def queryGDS(conf, rectLayer):
	gds = []
	gds_bloat = []
	if rectLayer in conf["materials"]:
		if "gds" in conf["materials"][rectLayer]:
			gds = conf["materials"][rectLayer]["gds"]
		if "gds_bloat" in conf["materials"][rectLayer]:
			gds_bloat = conf["materials"][rectLayer]["gds_bloat"]
	else:
		if rectLayer+"_gds" in conf["materials"]["metal"]:
			gds = conf["materials"]["metal"][rectLayer+"_gds"]
		if rectLayer+"_gds_bloat" in conf["materials"]["metal"]:
			gds_bloat = conf["materials"]["metal"][rectLayer+"_gds_bloat"]
	return zip(gds, gds_bloat)

TAP, FILL, CELL, BLOCK = range(4)

class Rect:
	def __init__(self, label, layer, bounds, hint="", isInput=False, isOutput=False):
		self.label = label
		self.layer = layer
		self.bounds = [int(bound) for bound in bounds]
		self.hint = hint
		self.isInput = isInput
		self.isOutput = isOutput

def isIn(searches, string):
	for search in searches:
		if search in string:
			return True
	return False

class Cell:
	def __init__(self, name, kind, bbox, rects):
		self.name = name
		self.kind = kind
		self.bbox = bbox
		self.rects = rects

def readCell(path):
	name = os.path.splitext(os.path.basename(path))[0]
	kind = BLOCK
	if "welltap" in name.lower():
		kind = TAP
	elif "fill" in name.lower():
		kind = FILL	
	elif "cell" in name.lower():
		kind = CELL

	# left, bottom, right, top
	bbox = [0, 0, 1, 1]
	rects = []

	with open(path, "r") as rf:
		for number, line in enumerate(rf):
			args = [arg.strip() for arg in line.split(" ")]
			if args[0] == "bbox":
				bbox = [int(arg) for arg in args[1:]]
			else:
				isInput = (args[0] == "inrect")
				isOutput = (args[0] == "outrect")
				hint = ""
				if len(args) >= 8:
					hint = args[7]

				rects.append(Rect(args[1], args[2], [int(arg) for arg in args[3:7]], hint, isInput, isOutput))
	return Cell(name, kind, bbox, rects)

def writeLayerMap(path, conf):
	layers = zip(conf["gds"]["layers"], conf["gds"]["major"], conf["gds"]["minor"])
	with open(path, "w") as fptr:
		for layer in layers:
			name, purpose = layer[0].rsplit(".", 1)
			if "via" in name and purpose in ["drawing", "dg", "drw"]:
				print(f"{name} VIA {layer[1]} {layer[2]}", file=fptr)
			elif purpose in ["drawing", "dg", "drw"]:
				print(f"{name} LEFOBS {layer[1]} {layer[2]}", file=fptr)
			elif purpose in ["label", "ll", "lbl"]:
				print(f"NAME {name}/PINNAME {layer[1]} {layer[2]}", file=fptr)
				print(f"NAME {name}/PIN {layer[1]} {layer[2]}", file=fptr)
				print(f"NAME {name}/LEFPINNAME {layer[1]} {layer[2]}", file=fptr)
				print(f"NAME {name}/LEFPIN {layer[1]} {layer[2]}", file=fptr)
			elif purpose in ["net", "nt"]:
				print(f"{name} NET {layer[1]} {layer[2]}", file=fptr)
			elif purpose in ["pin", "pin1", "pn"]:
				print(f"{name} PIN,LEFPIN {layer[1]} {layer[2]}", file=fptr)
			elif purpose in ["blockage", "be", "blo"]:
				print(f"{name} BLOCKAGE {layer[1]} {layer[2]}", file=fptr)
			if "prb" in name.lower():
				print(f"DIEAREA ALL {layer[1]} {layer[2]}", file=fptr)

def writeGDS(path, conf, cell):
	if not hasGDSTK:
		print("gdstk not found, skipping gds export")
		return

	scale = conf["general"]["scale"]
	numMetals = conf["general"]["metals"]
	layers = {layer: (major, minor) for layer, major, minor in zip(conf["gds"]["layers"], conf["gds"]["major"], conf["gds"]["minor"])}
	
	lib = gdstk.Library()
	gdsCell = lib.new_cell(cell.name)
	
	bndry = None
	for layer, idx in layers.items():
		if layer.startswith("prb"):
			bndry = idx
			break
	if bndry:
		gdsCell.add(gdstk.rectangle((cell.bbox[0]*scale, cell.bbox[1]*scale), (cell.bbox[2]*scale, cell.bbox[3]*scale), layer=bndry[0], datatype=bndry[1]))
	for rect in cell.rects:
		gds = queryGDS(conf, rect.layer)
		labelWritten = False
		for layerName, bloat in gds:
			name, purpose = layerName.rsplit(".", 1)
			if layerName in layers:
				idx = layers[layerName]
				gdsCell.add(gdstk.rectangle(((rect.bounds[0]-bloat)*scale, (rect.bounds[1]-bloat)*scale), ((rect.bounds[2]+bloat)*scale, (rect.bounds[3]+bloat)*scale), layer=idx[0], datatype=idx[1]))
				if rect.label and rect.label != "#" and not labelWritten:
					gdsCell.add(gdstk.Label(rect.label, ((rect.bounds[0] + rect.bounds[2])*scale/2, (rect.bounds[1] + rect.bounds[3])*scale/2), layer=idx[0], texttype=idx[1]))
					labelWritten = True

	lib.write_gds(path)

def writeLEF(path, conf, cell):
	scale = conf["general"]["scale"]
	numMetals = conf["general"]["metals"]
	with open(path, "w") as fptr:
		print(f"MACRO {cell.name}", file=fptr)
		if cell.kind == TAP:
			print("CLASS CORE WELLTAP ;", file=fptr)
		elif cell.kind == FILL:
			print("CLASS CORE SPACER ;", file=fptr)
		elif cell.kind == CELL:
			print("CLASS CORE ;", file=fptr)
		else:
			print("CLASS BLOCK ;", file=fptr)

		print(f"\tORIGIN {-cell.bbox[0]*scale} {-cell.bbox[1]*scale} ;", file=fptr)
		print(f"\tFOREIGN {cell.name} {cell.bbox[0]*scale} {cell.bbox[1]*scale} ;", file=fptr)
		print(f"\tSIZE {(cell.bbox[2]-cell.bbox[0])*scale} BY {(cell.bbox[3]-cell.bbox[1])*scale} ;", file=fptr)
		print(f"\tSYMMETRY X Y ;", file=fptr)
		if cell.kind in [FILL, TAP, CELL]:
			print("\tSITE CoreSite ;", file=fptr)

		for rect in cell.rects:
			if rect.isInput or rect.isOutput:
				direction = "INOUT"
				if not rect.isInput:
					direction = "OUTPUT"
				elif not rect.isOutput:
					direction = "INPUT"

				print(f"\tPIN {rect.label}", file=fptr)
				if isIn(["vnsub", "vpsub", "vddsub", "vsssub", "vddb", "vssb"], rect.label.lower()):
					print("\t\tDIRECTION INOUT ;", file=fptr)
					print("\t\tUSE POWER ;", file=fptr)
				elif isIn(["vdd", "pwr"], rect.label.lower()):
					print("\t\tDIRECTION INOUT ;", file=fptr)
					print("\t\tUSE POWER ;", file=fptr)
					if cell.kind in [FILL, TAP, CELL]:
						print("\t\tSHAPE ABUTMENT ;", file=fptr)
				elif isIn(["gnd", "vss"], rect.label.lower()):
					print("\t\tDIRECTION INOUT ;", file=fptr)
					print("\t\tUSE GROUND ;", file=fptr)
					if cell.kind in [FILL, TAP, CELL]:
						print("\t\tSHAPE ABUTMENT ;", file=fptr)
				else:
					print(f"\t\tDIRECTION {direction} ;", file=fptr)
					print(f"\t\tUSE SIGNAL ;", file=fptr)

				print("\t\tPORT", file=fptr)
				gds = queryGDS(conf, rect.layer)
				for layer, bloat in gds:
					name, purpose = layer.rsplit(".", 1)
					print(f"\t\t\tLAYER {name} ;", file=fptr)
					print(f"\t\t\t\tRECT {(rect.bounds[0]-bloat)*scale} {(rect.bounds[1]-bloat)*scale} {(rect.bounds[2]+bloat)*scale} {(rect.bounds[3]+bloat)*scale} ;", file=fptr)
				print("\t\tEND", file=fptr)
				print(f"\tEND {rect.label}", file=fptr)

		print("\tOBS", file=fptr)
		for rect in cell.rects:
			#if not rect.isInput and not rect.isOutput:
			gds = queryGDS(conf, rect.layer)
			for layer, bloat in gds:
				name, purpose = layer.rsplit(".", 1)
				print(f"\t\tLAYER {name} ;", file=fptr)
				print(f"\t\t\tRECT {(rect.bounds[0]-bloat)*scale} {(rect.bounds[1]-bloat)*scale} {(rect.bounds[2]+bloat)*scale} {(rect.bounds[3]+bloat)*scale} ;", file=fptr)
		print("\tEND", file=fptr)
		print(f"END {cell.name}", file=fptr)
		print("", file=fptr)

def print_help():
	print("Usage: rect2lef.py [options] <input.rect>")
	print("\t-T<tech>\tidentify the technology used for this translation.")
	print("\t-lm\temit the layermap")
	print("\t-gds\twrite the gds.")

if __name__ == "__main__":
	if len(sys.argv) <= 2 or sys.argv[1] == '--help' or sys.argv[1] == '-h':
		print_help()
	else:
		rectPath = None
		doLM = False
		doGDS = False
		techName = "sky130"
		actHome = os.environ.get('ACT_HOME', "/opt/cad")
		for arg in sys.argv[1:]:
			if arg[0] == '-':
				if arg[1] == 'T':
					techName = arg[2:]
				elif arg == "-lm":
					doLM = True
				elif arg == "-gds":
					doGDS = True
				else:
					print(f"error: unrecognized option '{arg}'")
					print("")
					print_help()
					sys.exit()
			elif not rectPath:
				rectPath = arg

		conf = loadActConf(actHome + "/conf/" + techName + "/layout.conf")
		if rectPath:
			cell = readCell(rectPath)
			writeLEF(cell.name + ".lef", conf, cell)
		if doLM:
			writeLayerMap("layermap.txt", conf)
		if doGDS:
			writeGDS(cell.name + ".gds", conf, cell) 
