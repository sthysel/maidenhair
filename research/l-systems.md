# L-Systems Primer

A practical guide to understanding and writing L-system grammars, with
a focus on the turtle interpretation used in Maidenhair.

## What is an L-system?

An L-system (Lindenmayer system) is a parallel string rewriting system.
You start with an initial string (the **axiom**) and apply **production
rules** simultaneously to every character, for a number of **iterations**.
The resulting string is then interpreted as drawing commands by a
**turtle** that moves through 3D space.

The key insight: a simple set of rules, applied repeatedly, produces
complex self-similar structures that closely resemble real plants.

## The basics

### Axiom

The starting string. Everything grows from this.

```
axiom = "F"
```

### Production rules

Each rule replaces a single character with a string. All rules are
applied **in parallel** — every character in the string is replaced
simultaneously in each iteration.

```
F = "FF+[+F-F-F]-[-F+F+F]"
```

Characters without a rule pass through unchanged (identity).

### Iteration

The axiom is rewritten `n` times. Each iteration makes the string
longer and the resulting structure more detailed.

```
Iteration 0:  F
Iteration 1:  FF+[+F-F-F]-[-F+F+F]
Iteration 2:  (each F in iteration 1 is replaced again...)
```

String length grows exponentially. A rule like `F → FF` doubles the
string every iteration. At iteration 7, that's 128 F symbols. A rule
like `F → F[+F]F[-F]F` produces 5 F's per input F — at iteration 5
that's 5^5 = 3125.

## Turtle interpretation

The final string is interpreted by a **turtle** — an imaginary cursor
that moves through 3D space, drawing lines as it goes. Each character
in the string is a command.

### Movement

| Symbol | Action |
|--------|--------|
| `F` | Move forward one step, **drawing** a branch segment |
| `f` | Move forward one step, **no drawing** (invisible advance) |

With parameters: `F(2.5)` moves forward 2.5 units. Without parameters,
the default `step_length` is used.

### Rotation

All angles are in degrees.

| Symbol | Axis | Direction |
|--------|------|-----------|
| `+` | Yaw | Turn left (around the up axis) |
| `-` | Yaw | Turn right |
| `&` | Pitch | Tilt down (nose down) |
| `^` | Pitch | Tilt up |
| `/` | Roll | Roll clockwise |
| `\` | Roll | Roll counter-clockwise |

With parameters: `+(45)` turns left 45°. Without parameters, the
default `angle_default` is used.

**Yaw** (`+`/`-`) is the most common — it creates 2D branching patterns
in a single plane. To make 3D structures, you need **pitch** (`&`/`^`)
and **roll** (`/`).

### Branching

| Symbol | Action |
|--------|--------|
| `[` | **Push** — save the turtle's position, orientation, and radius to a stack |
| `]` | **Pop** — restore the most recently saved state |

This is how branches work. The turtle walks along the main stem, pushes
its state, walks along a branch, pops back to the main stem, and
continues.

```
F[+F]F[-F]F

Reads as:
  F       move forward (trunk)
  [       save position
  +F      turn left, move forward (left branch)
  ]       return to trunk
  F       move forward (trunk continues)
  [       save position
  -F      turn right, move forward (right branch)
  ]       return to trunk
  F       move forward (trunk tip)
```

### Decoration

| Symbol | Action |
|--------|--------|
| `!` | Reduce branch radius by `radius_ratio` (makes branches thinner) |
| `~` | Emit a leaf at the current position |

## Parametric symbols

Symbols can carry numeric parameters in parentheses:

```
F(2.5)    move forward 2.5 units
+(30)     turn left 30 degrees
F(0.8)    move forward 0.8 units
```

When a symbol has no parameter, the default from the preset's
`[params]` section is used. In Maidenhair, `step_length` acts as a
**scale factor** — `F(0.5)` moves `0.5 × step_length` units.

## Building a grammar

### Step 1: Start simple

The simplest interesting plant:

```
axiom = "F"
F = "F[+F]F[-F]F"
angle_default = 25.7
```

At iteration 1: `F[+F]F[-F]F` — a trunk with two side branches.
At iteration 3: a recognisable bushy plant.

### Step 2: Separate structure from detail

Use non-turtle symbols as **rewriting variables**. Characters like `A`,
`B`, `X` are rewritten by rules but **ignored** by the turtle (they
don't cause any movement or drawing). This lets you control the
branching pattern separately from the drawing.

```
axiom = "X"
X = "F[+X]F[-X]+X"
F = "FF"
```

Here `X` controls the branching pattern (where to branch, at what
angles) and `F` controls the segment length (doubling each iteration).
The turtle only sees `F`, `+`, `-`, `[`, `]` — it ignores `X`.

This is **node rewriting** vs **edge rewriting**:
- **Edge rewriting**: rules replace turtle commands (`F → FF+F`)
- **Node rewriting**: rules replace abstract symbols (`X → F[+X][-X]FX`)

Node rewriting gives you more control over the structure.

### Step 3: Add depth with multiple symbols

For compound structures like ferns, use multiple rewriting symbols at
different levels:

```
axiom = "A"
A = "F[+B]F[-B]FA"       # main axis produces B branches
B = "F[+C]F[-C]FB"       # secondary branches produce C
C = "f[+~]f[-~]C"        # terminal branches produce leaves
```

Each iteration, `A` grows the main stem and adds `B` branches. `B`
grows and adds `C` sub-branches. `C` grows and adds leaves. After
enough iterations, you get a multi-level compound leaf structure.

### Step 4: Make it 3D

2D plants only use `+` and `-` (yaw). For 3D:

- **`/(137)`** — roll 137.5° between branch pairs. This is the
  **golden angle**, which distributes branches evenly around the stem
  (like sunflower seeds). It prevents branches from stacking on top of
  each other.
- **`&(angle)`** — pitch branches outward from the stem.
- **`!`** — reduce radius at branch points for natural taper.

```
axiom = "FA"
A = "F!![+(45)&(10)B]/(137)F[-(45)&(10)B]/(137)FA"
B = "F![+C]F[-C]!FB"
C = "f[+~]f[-~]C"
```

### Step 5: Tropism

Tropism bends every forward step slightly toward gravity (-Y). This
makes trees droop and fern fronds arch, rather than growing as rigid
wire structures. Controlled by the `tropism_weight` parameter.

- `0.0` — no gravity, rigid growth
- `0.1–0.2` — gentle arching, good for ferns
- `0.3+` — heavy drooping, weeping willow effect

Tropism only works when the turtle isn't heading straight up or down
(the cross product of heading and gravity must be non-zero to define a
bend direction).

## Classic examples

### Algae (Lindenmayer's original, 1968)

Not graphical, but the first L-system ever:

```
axiom = "A"
A = "AB"
B = "A"
```

```
Gen 0: A
Gen 1: AB
Gen 2: ABA
Gen 3: ABAAB
Gen 4: ABAABABA
```

The string lengths follow the Fibonacci sequence.

### Koch curve

```
axiom = "F"
F = "F+F-F-F+F"
angle_default = 90
```

Produces a fractal snowflake-like curve.

### Sierpinski triangle

```
axiom = "A"
A = "B-A-B"
B = "A+B+A"
angle_default = 60
```

### Fractal plant (ABOP Figure 1.24f)

```
axiom = "X"
X = "F-[[X]+X]+F[+FX]-X"
F = "FF"
angle_default = 22.5
```

One of the most recognisable L-system plants. 2D, bushy, fern-like.

### Fractal plant (ABOP Figure 1.24c)

```
axiom = "F"
F = "FF+[+F-F-F]-[-F+F+F]"
angle_default = 22.5
```

The simplest single-rule plant that looks natural.

### 3D bush (ABOP Figure 1.25)

```
axiom = "A"
A = "[&FL!A]/////[&FL!A]///////[&FL!A]"
F = "S/////F"
S = "FL"
L = "~"
angle_default = 22.5
```

Each `/////` is five 22.5° rolls = 112.5° between branches.

### Maidenhair fern (Maidenhair project)

```
axiom = "F(1)F(1)A"
A = "F(0.5)!![+(48)&(10)B]/(137)F(0.5)[-(48)&(10)B]/(137)A"
B = "F(0.25)![+(35)C]F(0.25)[-(35)C]!B"
C = "f(0.08)[+(22)~][-(22)~]C"
```

Tripinnate compound leaf:
- `A` = main rachis: alternating primary pinnae with golden-angle roll
- `B` = primary pinna: alternating secondary sub-pinnae
- `C` = secondary pinna: dense fan-shaped leaflets
- `!` thins the radius at each branching level
- `&(10)` tilts pinnae slightly outward
- `/(137)` golden-angle roll spreads pinnae in 3D

## Design patterns

### Alternating branches

```
A = "F[+B]F[-B]FA"
```

Branches alternate left and right along the stem. The trailing `A`
continues the stem.

### Golden-angle phyllotaxis

```
A = "F[+B]/(137)F[-B]/(137)FA"
```

The `/(137)` roll between each pair distributes branches evenly in 3D.
137.5° is the golden angle — no two branches ever align.

### Progressive thinning

```
A = "F!!B"
```

Each `!` multiplies the radius by `radius_ratio`. Two `!!` squares the
thinning. This creates natural taper from thick trunks to thin twigs.

### Terminal ornaments

```
B = "F[+~][-~]FB"    # leaves at every node
C = "f[+~][-~]~"     # terminal cluster of leaves (non-recursive)
```

Non-recursive rules (`C` doesn't contain `C`) produce terminal
structures. Recursive rules (`B` contains `B`) produce growing axes.

### Stochastic variation

When a symbol has multiple possible replacements, one is chosen
randomly (weighted by probability):

```
[grammar.stochastic]
F = [[0.5, "F[+F]F"], [0.5, "F[-F]F"]]
```

Each `F` has a 50/50 chance of branching left or right. Use a fixed
`seed` for reproducibility.

## Debugging tips

1. **Start at iteration 1** — check that the first expansion looks right
   before going higher.
2. **Print the derivation string** — `uv run python -c "..."` to see
   what the grammar produces.
3. **Use the live editor** — type rules in the sidebar and see results
   immediately.
4. **Check brackets** — every `[` must have a matching `]`. Unmatched
   brackets cause the stack to underflow or leave the turtle in the
   wrong position.
5. **Watch string length** — it grows exponentially. If the app hangs,
   reduce iterations. The `max_string_length` guard (default 50M chars)
   catches runaway grammars.
6. **2D vs 3D** — if your plant looks flat, you're only using `+`/`-`.
   Add `/` (roll) and `&`/`^` (pitch) for 3D structure.

## References

- Prusinkiewicz & Lindenmayer, *The Algorithmic Beauty of Plants* (1990)
  — the definitive reference. Free PDF: `research/abop.pdf`
- Chapter 1 covers the basics (string rewriting, turtle interpretation,
  bracketed L-systems)
- Chapter 3 covers parametric L-systems
- Chapter 8 covers fractal plant development models
