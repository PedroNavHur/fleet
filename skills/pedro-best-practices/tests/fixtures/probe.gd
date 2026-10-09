extends Node
class_name Probe

signal done(value: int)
@export var speed: float = 1.0

func pick(a: int, b: bool, c: bool) -> int:
	if a > 1 and b && c:
		for x in [1, 2]:
			if x or b:
				return x
	elif a < 0:
		return 2 if a else 3
	else:
		match a:
			1:
				return 1
			_:
				pass
	while a > 0:
		a -= 1
	var f := func(x: int) -> int: return 1 if x else 0
	return pick(a - 1, not b, c)

static func helper(n: int) -> int:
	return n

class Inner:
	func m(n: int) -> int:
		return self.m(n - 1) if n else 0
