# Introduction

The intermediate palette generates a 2D discrete color field $`\mathbf{C}: \mathcal{G} \rightarrow [0, 255]^3`$ over a rectangular grid of cells:

$$
\mathcal{G} = \left\lbrace (r, c) \in \mathbb{Z}^2 \middle\vert 0 \le r < R,  0 \le c < C \right\rbrace
$$

where $`R`$ is the total number of rows and $`C`$ is the total number of columns. Dealing with $`R=C`$ just for ease of development.

A user pins an arbitrary subset of $`K`$ cells of **anchors** onto $`\mathcal{G}`$:

$$
\mathcal{A} = \left\lbrace \left( \mathbf{p}_k, \mathbf{C}\_k \right) \right\rbrace\_{k=1}^K, \quad \mathbf{p}_k = (r_k, c_k) \in \mathcal{G}, \quad \mathbf{C}_k \in [0, 255]^3
$$

The goal is to calculate the color $`\mathbf{C}(r, c)`$ of every unpinned cell $`(r, c) \in \mathcal{G} \setminus \lbrace \mathbf{p}_k \rbrace`$.

# Some terminologies

$`\mathbf{LI}`$, an abbreviation of [linear interpolation](https://en.wikipedia.org/wiki/Linear_interpolation), is a function that takes two values $`A`$ and $`B`$ and a weight parameter $`t`$ and converts it into their linear interpolation which defined as

$$
\mathbf{LI}(A,B,t) = (1-t)A + tB.
$$

Let $`\mathbf{a}_r = [r^{(0)}, r^{(1)}, \ldots, r^{(N-1)}]`$ and $`\mathbf{a}_c = [c^{(0)}, c^{(1)}, \ldots, c^{(M-1)}]`$ be respectively two sorted index sets of the sets $`\lbrace r_1, r_2, \ldots, r_K \rbrace \cup \lbrace 0, R-1 \rbrace`$ and $`\lbrace c_1, c_2, \ldots, c_K \rbrace \cup \lbrace 0, C-1 \rbrace`$. Let $`\mathbf{a}_r \times \mathbf{a}_c`$ be the set of **junctions**. Our grid $`\mathcal{G}`$ can be partitioned by junctions into an $`(N-1) \times (M-1)`$ grid of **patches** $`\mathcal{P}`$ such that $`\mathcal{P}_{i,j} = [r^{(i)}, r^{(i+1)}] \times [c^{(j)}, c^{(j+1)}]`$. In layman terms, junctions are grids where anchors + corners meet horizontally and vertically, while patches are blocks of grids formed by those junctions.  

The term **bilinear patch blend values** refer to values $`t_{r,c} \in [0, 1]`$ that were determined *locally* on $`\mathcal{P}_{i,j}`$ (only dependent on the patch) where $`(r,c) \in \mathcal{P}_{i,j}`$ for each grid $`(r,c)`$ in $`\mathcal{G}`$ or through some *subpatch* of $`\mathcal{P}`$.

The term **normalized spatial weight vectors** refer to vectors $`\mathbf{w}_{r,c}`$ such that 

$$
\mathbf{w}_{r, c} = \left[ w_{r,c}^{(1)}, \, w_{r,c}^{(2)}, \, \ldots, \, w_{r,c}^{(K)} \right]^T \in \Delta^{K-1}, \quad \sum_{k=1}^K w_{r,c}^{(k)} = 1, \quad w_{r,c}^{(k)} \ge 0
$$

where $`\Delta^{K-1}`$ is the unit $`(K-1)`$-simplex[^1].

Given color transformation $`\Phi`$ and a fixed number of weights $`L`$, **color mixing** is the transformation

$$
\mathbf{C}_{\text{mix}}(r, c) = \Phi^{-1} \left( \sum_{l=1}^L s_l(r, c) \Phi(\mathbf{C}_l) \right)
$$

where $`s_l \in [0,1], 1 \leq l \leq L`$ and $`\Sigma s_l = 1`$. The weights are, for example,
- Bilinear patch blend values: $`L=2`$ where $`s_1 = 1-t`$ and $`s_2 = t`$.
- Normalized spatial weight vectors: $`L = K`$ where $`s_l(r,c) = w_{r,c}^{(l)}`$ for $`1 \leq l \leq K`$.

# Solvers and mixers

This plugin uses decoupling strategy that separates spatial problem and the color mixing problem which allows degrees of freedom for the user. To clarify:
- **Grid solvers** deals with calculating weights (how the color of the anchors affects each location of the grid) given the locations of the anchors. It determines *where* exactly the colors came from. For example, this plugin's solvers either looks for the bilinear patch blend values (locally in a patch/subpatch) or the normalized spatial weight vectors (globally across all anchors).
- **Color mixers** evaluates colors onto singular continuous color models such as sRGB, linear RGB, Oklab and so on, combines them in the transformed model, and then translates them back into sRGB. See the color mixing transformation equation.

## Solvers

1. Linear Interpolation with Heuristic Voronoi Fallback. Heuristically interpolate values at junction if it is bounded by other two anchors vertically/horizontally, if not then it is determined as the color of the nearest anchor. The patches are then calculated with linear interpolation. Legacy from forked.
2. Steady-State Heat Equation (Laplacian). See [heat equation](https://en.wikipedia.org/wiki/Heat_equation). Colors at junctions are treated as an initial submatrix and is calculated towards its steady-state matrix, and then the matrix (junctions) are used to linearly interpolate the patches. Mostly for performance sake.
3. Coons Grid-Line Patching Interpolation. See [Coons patch](https://en.wikipedia.org/wiki/Coons_patch). 
   1. The corners of the grid, if not anchored, are defaulted to the nearest anchor and will act as a temporary anchor. 
   2. 1D piecewise linear interpolation for the boundaries of the grid is then calculated.
   3. 1D piecewise linear interpolation for the horizontal and vertical lines of junctions is then calculated.
   4. Finally, the grid is then divided into patches $`\mathcal{P}`$ each interpolated with Coons patch.

   Good for creating patchy palettes.
4. Shepard's Method (Inverse Distance Weighting). See [inverse distance weighting](https://en.wikipedia.org/wiki/Inverse_distance_weighting) especially Shephard's method with a quadratic decay exponent $`p=2`$. Sometimes Laplacian isn't enough.

## Mixers

1. sRGB. The transformation is simply the identity map.
2. Linear sRGB. This uses the sRGB Electro-Optical Transfer Function (EOTF) as the transformation.
3. Oklab. See [Oklab wikipedia](https://en.wikipedia.org/wiki/Oklab_color_space) and refer to "Conversion to sRGB". 
4. OKLCH. See [Oklab wikipedia](https://en.wikipedia.org/wiki/Oklab_color_space) and refer to "Conversion to and from Oklch". A bit finnicky to use in terms of color mixing.

[^1]: https://en.wikipedia.org/wiki/Simplex
