#!/usr/bin/python3

import sys
from math import trunc

# lvtnfet d g s b
# 
class Transistor:
	def __init__(self,
			inst,
			kind,
			gate,
			source,
			drain,
			bulk,
			width = 1,
			length = 1):
		self.inst = inst
		self.kind = kind
		self.gate = gate
		self.source = source
		self.drain = drain
		self.bulk = bulk
		self.width = width
		self.length = length
		self.shared_source = list()
		self.shared_drain = list()
	
	def emit(self, sources, tab = ''):
		if self.drain in sources or self.drain[0] == '@':
			self.flip()

		if self.source in sources:
			if self.kind == 'n':
				fmt = tab + '{gate}<{width:.1f},{length:.1f}> -> {drain}-'
			elif self.kind == 'p':
				fmt = tab + '~{gate}<{width:.1f},{length:.1f}> -> {drain}+'
		elif self.source[0] == '@':
			if self.kind == 'n':
				fmt = tab + '~{source} & {gate}<{width:.1f},{length:.1f}> -> {drain}-'
			elif self.kind == 'p':
				fmt = tab + '{source} & ~{gate}<{width:.1f},{length:.1f}> -> {drain}+'
		else:
			fmt = tab + 'pass{kind}<{width:.1f},{length:.1f}>({gate}, {source}, {drain})'
			#fmt = tab + '{gate}<{width:.1f},{length:.1f}> -> {drain} := {source}'

		return fmt.format(
				kind=self.kind,
				width=trunc(self.width),
				length=trunc(self.length),
				gate=self.gate,
				source=self.source,
				drain=self.drain)


	def emit_expr(self):
		return '{kind}{gate}<{width:.1f},{length:.1f}>'.format(
			kind = '~' if self.kind == 'p' else '',
			gate = self.gate,
			width = trunc(self.width),
			length = trunc(self.length))

	def ports(self):
		result = [self.bulk, self.gate]
		if self.source[0] != '@':
			result.append(self.source)
		if self.drain[0] != '@':
			result.append(self.drain)

		return list(set(result))

	def gates(self):
		return [self.gate]

	def flip(self):
		self.source,self.drain = self.drain,self.source
		self.shared_source,self.shared_drain = self.shared_drain,self.shared_source

class Expr:
	def __init__(self,
			op,
			kind,
			source,
			drain,
			bulk = '',
			devs = None):	
		self.op = op
		self.kind = kind
		self.source = source
		self.drain = drain
		self.bulk = bulk
		if devs:
			self.devs = devs
		else:
			self.devs = list()
		self.shared_source = list()
		self.shared_drain = list()
	
	def emit_expr(self):
		return (' ' + self.op + ' ').join([
			'(' + dev.emit_expr() + ')'
				if isinstance(dev, Expr) and dev.op == '|'
				else dev.emit_expr()
				for dev in self.devs])

	def emit(self, sources, tab = ''):
		if self.drain in sources or self.drain[0] == '@':
			self.flip()
		
		if self.source in sources:
			if self.kind == 'n':
				return tab + self.emit_expr() + ' -> ' + self.drain + '-'
			elif self.kind == 'p':
				return tab + self.emit_expr() + ' -> ' + self.drain + '+'
		elif self.source[0] == '@':
			if self.kind == 'n':
				return tab + '~' + self.source + ' & (' + self.emit_expr() + ') -> ' + self.drain + '-'
			elif self.kind == 'p':
				return tab + self.source + ' & (' + self.emit_expr() + ') -> ' + self.drain + '+'
		else:
			return '\n'.join([dev.emit(sources, tab) for dev in self.devs])
			#return tab + self.emit_expr() + ' -> ' + self.drain + ' := ' + self.source

	def gates(self):
		result = list()
		for dev in self.devs:
			result += dev.gates()
		return list(set(result))

	def ports(self):
		result = [self.bulk]
		if self.source[0] != '@':
			result.append(self.source)
		if self.drain[0] != '@':
			result.append(self.drain)

		result += self.gates()

		return list(set(result))

	def flip(self):
		self.source,self.drain = self.drain,self.source
		self.shared_source,self.shared_drain = self.shared_drain,self.shared_source
		for dev in self.devs:
			dev.flip()
		self.devs.reverse()

class Instance:
	def __init__(self,
			name,
			typename,
			ports = None):
		self.name = name
		self.typename = typename
		if ports:
			self.ports = ports
		else:
			self.ports = list()

	def emit(self, tab = ''):
		if self.ports:
			return tab + '{typename} {name}({ports});'.format(
				typename = self.typename,
				name = self.name,
				ports = ', '.join(self.ports))
		else:
			return tab + self.typename + ' ' + self.name + ';'

def can_merge(left, right, sources):
	return left == right or (left in sources or left and left[0] == '@') and (right in sources or right and right[0] == '@')

class Process:
	def __init__(self,
			name,
			ports = None,
			nets = None,
			devs = None,
			use_globals = False):
		self.name = name
		self.use_globals = use_globals
		if self.use_globals:
			self.vdd = 'g.Vdd'
			self.gnd = 'g.GND'
			self.vdds = 'g.vpsub'
			self.gnds = 'g.vnsub'
		else:
			self.vdd = None
			self.gnd = None
			self.vdds = None
			self.gnds = None

		self.ports = list()
		self.add_ports(ports)
		self.nets = list()
		self.add_nets(nets)
		self.devs = list()
		self.add_devs(devs)
		self.insts = list()

	@property 
	def sources(self):
		return [x for x in [self.vdd, self.gnd, self.vdds, self.gnds] if not x is None]

	def check(self, names):
		if names is not None:
			if isinstance(names, list):
				result = list()
				for name in names:
					result.extend(self.check(name))
				return result
			else:
				if 'vdds' in names.lower() or 'vpb' in names.lower() or 'vpsub' in names.lower() or names == self.vdds:
					if not self.vdds:
						self.vdds = names
					return [self.vdds]
				elif 'gnds' in names.lower() or 'vnb' in names.lower() or 'vnsub' in names.lower() or names == self.gnds:
					if not self.gnds:
						self.gnds = names
					return [self.gnds]
				elif 'vdd' in names.lower() or 'pwr' in names.lower() or names == self.vdd:
					if not self.vdd:
						self.vdd = names
					return [self.vdd]
				elif 'gnd' in names.lower() or names == self.gnd:
					if not self.gnd:
						self.gnd = names
					return [self.gnd]
				else:
					return [names.replace("#","")]
		return []

	def add_ports(self, ports):
		if self.use_globals:
			self.ports.extend([x for x in self.check(ports) if x not in self.sources])
		else:
			self.ports.extend(self.check(ports))

	def add_nets(self, nets):
		self.nets.extend([x for x in self.check(nets) if x not in self.sources])

	def check_devs(self, devs):
		if devs is not None:
			if isinstance(devs, list):
				result = list()
				for dev in devs:
					result.extend(self.check_devs(dev))
				return result
			else:
				devs.source = self.check(devs.source)[0]
				devs.drain = self.check(devs.drain)[0]
				devs.bulk = self.check(devs.bulk)[0]
				if isinstance(devs, Transistor):
					devs.gate = self.check(devs.gate)[0]
				if isinstance(devs, Expr):
					devs.devs = self.check_devs(devs.devs)
				return [devs]
		return []

	def add_devs(self, devs):
		self.devs.extend(self.check_devs(devs))

	def add_insts(self, insts):
		if insts is not None:
			if isinstance(insts, list):
				result = list()
				for inst in insts:
					self.add_inst(inst)
			else:
				insts.ports = self.check(insts.ports)
				self.insts.append(insts)

	def build_nets(self):
		for dev in self.devs:
			for port in dev.ports():
				if port not in self.ports and port not in self.nets and port not in self.sources:
					self.nets.append(port)

	def build_AND(self):
		nets = self.nets + [x for x in self.ports if x not in self.sources]
		for net in nets:
			source = list()
			drain = list()
			for dev in self.devs:
				if dev.source == net:
					source.append(dev)
				if dev.drain == net:
					drain.append(dev)
			
			lst = list()
			if len(source) == 1 and len(drain) == 1 and source[0].bulk == drain[0].bulk and source[0].kind == drain[0].kind:
				lst = drain+source
			elif len(source) == 2 and len(drain) == 0 and source[0].bulk == source[1].bulk and source[0].kind == source[1].kind:
				source.sort(key=lambda dev: dev.drain not in [self.vdd, self.gnd])
				source[0].flip()
				lst = source
			elif len(source) == 0 and len(drain) == 2 and drain[0].bulk == drain[1].bulk and drain[0].kind == drain[1].kind:
				drain.sort(key=lambda dev: dev.source not in [self.vdd, self.gnd])
				drain[1].flip()
				lst = drain

			if lst:
				self.devs.remove(lst[0])
				self.devs.remove(lst[1])
				self.nets.remove(net)
				devs = list()

				if isinstance(lst[0], Expr) and lst[0].op == '&':
					devs += lst[0].devs
				else:
					devs.append(lst[0])

				if isinstance(lst[1], Expr) and lst[1].op == '&':
					devs += lst[1].devs
				else:
					devs.append(lst[1])

				self.devs.append(Expr('&', lst[0].kind, lst[0].source, lst[1].drain, lst[0].bulk, devs))

	def build_OR(self):
		nets = self.nets + [x for x in self.ports if x not in self.sources] + self.sources
		for source in nets:
			for drain in nets:
				devs = dict()
				for dev in self.devs:
					if can_merge(dev.source, source, [self.vdd, self.gnd]) and dev.drain == drain:
						if dev.bulk not in devs:
							devs[dev.bulk] = [[dev], [], dev.kind]
						else:
							devs[dev.bulk][0].append(dev)
					elif can_merge(dev.drain, source, [self.vdd, self.gnd]) and dev.source == drain:
						if dev.bulk not in devs:
							devs[dev.bulk] = [[], [dev], dev.kind]
						else:
							devs[dev.bulk][1].append(dev)

				for bulk,dev in devs.items():
					if len(dev[0]) + len(dev[1]) > 1:
						for d in dev[0]:
							self.devs.remove(d)
						for d in dev[1]:
							self.devs.remove(d)
							d.flip()
						
						self.devs.append(Expr('|', dev[2], source, drain, bulk, dev[0] + dev[1]))

	def build_shared(self):
		nets = self.nets + [x for x in self.ports if x not in self.sources]
		for net in nets:
			source = list()
			drain = list()
			gate = list()
			for dev in self.devs:
				if dev.source == net:
					source.append(dev)
				if dev.drain == net:
					drain.append(dev)
				if net in dev.gates():
					gate.append(dev)
			
			if not gate and len(source) > 1 and len(drain) == 1 and source[0].bulk == drain[0].bulk and source[0].kind == drain[0].kind:
				if net in self.nets:
					self.nets.remove(net)
				for dev in source:
					dev.source = '@' + dev.source
					dev.shared_source = source
				for dev in drain:
					dev.drain = '@' + dev.drain
					dev.shared_drain = drain

	def build_exprs(self):
		done_shared = False
		while not done_shared:
			done_shared = True

			l = len(self.devs)+1
			while len(self.devs) < l:
				l = len(self.devs)
				self.build_AND()
				self.build_OR()
				if len(self.devs) < l:
					done_shared = False
			
			self.build_shared()
		
		self.devs.sort(key=lambda dev: [dev.drain, dev.kind])
	
	def emit(self, tab = ''):
		result = [tab + 'export defproc {name}({glob}bool {ports}) {{'.format(
			name = self.name,
			glob = "globals g; " if self.use_globals else "",
			ports = ', '.join(self.ports))]

		if self.nets:
			result += [tab + '\tbool ' + ', '.join(self.nets) + ';\n']

		for inst in self.insts:
			result.append(inst.emit(tab + '\t'))

		result.append('')
		result.append(tab + '\tprs <{vdd}, {gnd} | {vdds}, {gnds}> {{'.format(
			vdd = self.vdd,
			gnd = self.gnd,
			vdds = self.vdds,
			gnds = self.gnds))

		if self.devs:
			for dev in self.devs:
				devstr = dev.emit([self.vdd, self.gnd], tab + '\t\t')
				if devstr.strip():
					result.append(devstr)
	
		result.append(tab + '\t}')
		result.append(tab + '}\n')
		return result

def interpret_length(length):
	if length[-1] == 'm':
		return float(length[0:-1])*1e-3
	elif length[-1] == 'u':
		return float(length[0:-1])*1e-6
	elif length[-1] == 'n':
		return float(length[0:-1])*1e-9
	elif length[-1] == 'p':
		return float(length[0:-1])*1e-12
	elif length[-1] == 'f':
		return float(length[0:-1])*1e-15
	return float(length)

def print_help():
	print("Usage: spi2act.py [options] <lambda> <spice file>")
	print("\t--globals,-g\tbundles the power rails into a globals structure.")
	print("")
	print("Tech     Lambda")
	print("ibm10lp  0.025e-6")
	print("ibm12soi 0.019e-6")
	print("ibm28lp  0.015e-6")
	print("ibm9lp   0.05e-6")
	print("ibm9sf   0.04e-6")
	print("sam28lp  0.015e-6")
	print("st28soi  0.015e-6")
	print("tsmc65   0.03e-6")
	print("xlp2     0.075e-6")

if __name__ == "__main__":
	if len(sys.argv) <= 2 or sys.argv[1] == '--help' or sys.argv[1] == '-h':
		print_help()
	else:
		myproc = None
		scale = None
		in_path = None
		use_globals = False
		swap_source_drain = False
		for arg in sys.argv[1:]:
			if arg[0] == '-':
				if arg == '--globals' or arg == '-g':
					use_globals = True
				elif arg == '--swap' or arg == '-s':
					swap_source_drain = True
				else:
					print("error: unrecognized option '{arg}'".format(arg=arg))
					print("")
					print_help()
					sys.exit()
			elif not scale:
				scale = float(arg)
			elif not in_path:
				in_path = arg

		if use_globals:
			print("import \"globals.act\";")
			print("")

		with open(in_path, "r") as lines:
			for number, line in enumerate(lines):
				line = line.strip()
				if line:
					if '.subckt' in line.lower():
						subckt = line.split(' ')
						myproc = Process(name = subckt[1], ports = subckt[2:], use_globals = use_globals)
					elif '.ends' in line.lower():
						if myproc:
							myproc.build_nets()
							myproc.build_exprs()
							print('\n'.join(myproc.emit()))
							myproc = None
						else:
							print("error: dangling '.ends' on line " + str(number))
							sys.exit()
					elif line[0].lower() != '*':
						# this is a device definition
						line = line.replace(" =", "=")
						line = line.replace("= ", "=")
						devs = line.split(' ')
						attrs = dict()
						ports = list()
						instname = None
						typename = None
						for dev in devs:
							if '=' in dev:
								attr = dev.split('=')
								attrs[attr[0]] = attr[1]
							else:
								port = dev.split(':')
								ports.append(port[0])
						instname = ports[0]
						ports = ports[1:]

						if line[0].lower() == 'x':
							# this device is a subckt instantiation
							typename = ports[-1]
							ports = ports[:-1]
							
							if myproc and 'fet' in typename:
								# this subckt is a mosfet
								myproc.add_devs(Transistor(
									inst = instname,
									kind = 'p' if 'pfet' in typename else 'n',
									# .subckt  sky130_fd_pr__nfet_01v8 d g s b
									gate = ports[1],
									source = ports[2] if not swap_source_drain else ports[0],
									drain = ports[0] if not swap_source_drain else ports[2],
									bulk = ports[3],
									width = interpret_length(attrs['w'])/scale,
									length = interpret_length(attrs['l'])/scale))
							elif myproc and 'diode' not in typename:
								myproc.add_insts(Instance(
									name = instname,
									typename = typename,
									ports = ports))
						elif line[0].lower() == 'm':
							# this device is a transistor instantiation
							typename = ports[-1]
							ports = ports[:-1]
							if 'w' not in attrs or 'l' not in attrs:
								print(line)
							
							# this subckt is a mosfet
							myproc.add_devs(Transistor(
								inst = instname,
								kind = 'p' if 'pfet' in typename else 'n',
								gate = ports[1],
								source = ports[2] if not swap_source_drain else ports[0],
								drain = ports[0] if not swap_source_drain else ports[2],
								bulk = ports[3],
								width = interpret_length(attrs['w'])/scale,
								length = interpret_length(attrs['l'])/scale))

