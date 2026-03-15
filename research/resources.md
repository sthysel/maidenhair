# Maidenhair Research Resources

## Primary References

### The Algorithmic Beauty of Plants (ABOP)
- **Full book PDF**: <https://algorithmicbotany.org/papers/abop/abop.pdf>
- **Chapter 1 — Graphical Modeling Using L-systems**: <https://algorithmicbotany.org/papers/abop/abop-ch1.pdf>
- **Chapter 8 — Fractal Properties of Plants**: <https://algorithmicbotany.org/papers/abop/abop-ch8.pdf>
- Authors: Prusinkiewicz & Lindenmayer, 1990
- Licence: Freely available from algorithmicbotany.org for non-commercial use

### Key Papers from Prusinkiewicz et al.
- **Modeling plant development with L-systems**: <https://algorithmicbotany.org/papers/modeling-plant-development-with-l-systems.pdf>
- **Modelling Compound Leaves Using Implicit Contours** (CGI 1992): <https://algorithmicbotany.org/papers/leaves.cgi92.pdf>
- **Parametric L-systems and their application** (Hanan dissertation, 1992): <https://algorithmicbotany.org/papers/hanan.dis1992.pdf>

## L-System References and Tools

### Paul Bourke's L-System Reference
- <https://paulbourke.net/fractals/lsys/>
- Comprehensive list of L-system production rules for many plant forms

### fractal.garden — Interactive L-System Explorer
- Fern-1: <https://www.fractal.garden/l-system/fern-1>
- Fern-4: <https://www.fractal.garden/l-system/fern-4>

### L-Py / OpenAlea Framework
- Repository: <https://github.com/openalea/lpy>
- Research-grade Python L-system framework with PlantGL visualization
- Licence: CeCILL (GPL-compatible)

### Algorithmic Botany Website
- <https://algorithmicbotany.org/>
- Papers, software (vlab, lpfg, cpfg), and educational resources

## Adiantum Morphology References

### Botanical Descriptions
- **NC State Extension — Adiantum capillus-veneris**: <https://plants.ces.ncsu.edu/plants/adiantum-capillus-veneris/>
- **Missouri Botanical Garden — Adiantum capillus-veneris**: <https://www.missouribotanicalgarden.org/PlantFinder/PlantFinderDetails.aspx?taxonid=285802>
- **Lucid Central Fern Key — Adiantum capillus-veneris**: <https://apps.lucidcentral.org/ferns/text/entities/adiantum_capillusveneris.htm>

### Key Morphological Features for Modeling
- Bipinnate to tripinnate (2-3 branching levels)
- Cuneate-flabellate (wedge to fan-shaped) pinnules, 5-30mm
- Dichotomous (forking) venation in pinnules
- Wiry, glossy black stipes and rachis
- Fronds arching/pendant, 15-50cm total
- 3-6 pairs of primary pinnae, alternately arranged

## ABOP L-System Examples Used

### Figure 1.24 — Six Bracketed OL-System Plants (p.25)
| ID | n | δ | Axiom | Productions |
|----|---|---|-------|-------------|
| a | 5 | 25.7° | F | F → F[+F]F[-F]F |
| b | 5 | 20° | F | F → F[+F]F[-F][F] |
| c | 4 | 22.5° | F | F → FF-[-F+F+F]+[+F-F-F] |
| d | 7 | 20° | X | X → F[+X]F[-X]+X; F → FF |
| e | 7 | 25.7° | X | X → F[+X][-X]FX; F → FF |
| f | 5 | 22.5° | X | X → F-[[X]+X]+F[+FX]-X; F → FF |

### Figure 1.25 — 3D Bush with Filled Leaves (p.26)
```
n = 7, δ = 22.5°
ω: A
p1: A → [&FL!A]/////[&FL!A]///////[&FL!A]
p2: F → S/////F
p3: S → FL
p4: L → ['''^^{-f+f+f-|-f+f+f}]
```

### Compound Leaf Development Model (Ch.8)
```
p1: A → I[+A]I[-A]IA
p2: I → II
```
Extended with depth parameter for bi/tripinnate:
```
p1: A(d) : d > 0 → I[+(angle)A(d-1)]I[-(angle)A(d-1)]IA(d)
p2: A(d) : d == 0 → ~
p3: I → II
```
