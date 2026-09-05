# Object Knowledge: Material and Texture

## Before execution

Inspect material slots, texture roles, formats, dimensions, color space, normal
or mask semantics, target parameters, and replacement policy.

## After execution

Check material bindings, texture references, sRGB and compression/type settings,
resolution, parameters, Blend Mode, Shading Model, and missing dependencies.

## Evidence

Use asset metadata, material parameter reads, texture settings, dependency
queries, and render evidence only when state inspection is insufficient.
