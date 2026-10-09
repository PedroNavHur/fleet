function pick(a: number, b: boolean, c: boolean) {
  if (a > 1 && b && c) {        // if +1, && seq +1
    for (const x of [1, 2]) {   // for +2 (nesting 1)
      if (x || b) return x      // if +3 (nesting 2), || +1
    }
  } else if (a < 0) {           // else if +1
    return a ? 2 : 3            // ternary +2 (nesting 1)
  } else {                      // else +1
    try { a++ } catch { return 0 } // catch +2 (nesting 1)
  }
  return 1
}
function a1(a: number, b: boolean, c: boolean) { if (a > 1 && b && c) { return 1 } return 0 }
function a2(a: number) { if (a) { return 1 } else if (a < 0) { return 2 } else { return 3 } }
function a3(a: number) { if (a) { try { a++ } catch { return 0 } } return 1 }
function a4(a: number) { if (a) { return a ? 2 : 3 } return 1 }
function a5(b: boolean) { if (b) { for (const x of [1]) { if (x || b) return x } } return 0 }
function a6(a: number) { if (a) { } else if (a < 0) { return a ? 2 : 3 } return 1 }
function a7(a: number) { if (a) { } else { try { a++ } catch { return 0 } } return 1 }
function a8(a: number, b: boolean) { return a > 1 && b || !b && a < 3 }
function a9(a: number) { const f = (x: number) => { if (x) return 1; return 0 }; return f(a) }
function a10(a: number) { switch (a) { case 1: return 1; case 2: return 2; default: return 0 } }
function a11(a: number) { outer: for (const x of [1]) { for (const y of [2]) { if (x) continue outer; if (y) break outer } } return a }
function a12(a: number) { return a ?? 2 }
function a13(n: number): number { return n <= 1 ? 1 : n * a13(n - 1) }
function a14(a: number) { while (a) { a-- } do { a++ } while (a < 3); return a }
