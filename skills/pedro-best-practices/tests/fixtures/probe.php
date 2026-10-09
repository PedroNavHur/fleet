<?php
function pick($a, bool $b, ?bool $c): int {
    if ($a > 1 && $b && $c) {
        foreach ([1, 2] as $x) {
            if ($x || $b) return $x;
        }
    } elseif ($a < 0) {
        return $a ? 2 : 3;
    } else {
        try { $a++; } catch (Exception $e) { return 0; }
    }
    return 1;
}
function a8($a, $b) { return $a > 1 && $b || !$b && $a < 3; }
function a9($a) { $f = fn($x) => $x ? 1 : 0; $g = function ($x) { if ($x) { return 1; } return 0; }; return $f($a); }
function a10($a) { switch ($a) { case 1: return 1; case 2: return 2; default: return 0; } }
function a12($a) { return ($a ?? 2) ?: 3; }
function a13($n) { return $n <= 1 ? 1 : $n * a13($n - 1); }
function a15($a) { return match ($a) { 1, 2 => 'low', 3 => $a > 0 ? 'x' : 'y', default => 'n' }; }
function a16($a) { if ($a): $a++; elseif ($a > 2): $a--; else: $a = 0; endif; while ($a) { foreach ([1] as $x) { if ($x) { continue 2; } } } return $a; }
class K {
    public ?int $p = null;
    public function m(int $n): int { return $n ? $this->m($n - 1) : 0; }
    public static function s(int $n): int { return $n ? self::s($n - 1) : 0; }
    abstract protected function z(): void;
}
