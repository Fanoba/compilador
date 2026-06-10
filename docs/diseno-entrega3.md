# Diseño — Entrega 3: Máquina Virtual y Manejo de Memoria

**Fecha:** 2026-06-09
**Lenguaje:** Little Duck · **Herramientas:** Python + PLY (sin librerías adicionales)

## Problema

Extender el compilador de Little Duck (entrega 2: léxico, sintaxis, semántica y
cuádruplos con nombres) para que produzca representación intermedia basada en
**direcciones de memoria virtual**, y construir una **máquina virtual independiente**
(quack-virtual-machine) que cargue e interprete ese código intermedio.

## Convención de memoria virtual (vista en clase)

Cada región arranca en un índice base; cada tipo dentro de la región usa el siguiente "bloque".

| Segmento   | int   | float | str   | bool  | void |
|------------|-------|-------|-------|-------|------|
| Global     | 1000  | 2000  | 3000  | —     | 4000 |
| Local      | 7000  | 8000  | 9000  | —     | —    |
| Temporal   | 12000 | 13000 | —     | 14000 | —    |
| Constante  | 17000 | 18000 | 19000 | —     | —    |

- Global y constantes viven en **memoria global única** (no cambian de dirección).
- Local y temporal viven en el **activation record** de cada llamada (call stack).

## Arquitectura

```
compiler.py   Compilador completo: léxico + sintaxis + semántica +
              MemoryManager (direcciones) + emisión del IR.
              Expone compile_source(source) -> (ir_text | None, errores).
vm.py         Máquina virtual INDEPENDIENTE. Carga obj.txt y lo ejecuta.
              Corre sola: `python vm.py obj.txt`.
main.py       Orquestador: lee input.txt -> compila -> si OK, escribe
              obj.txt + salida_debug.txt y ejecuta la VM.
input.txt     Único source code de entrada.
obj.txt       IR en direcciones (ejecutado por la VM).
salida_debug.txt  IR en nombres (para depuración / reporte).
```

## Operadores de cuádruplos (convención de clase)

`gotomain, =, +, -, *, /, >, <, >=, <=, ==, !=, gotof, gotot, goto, print,
newline, sub, param, gosub, endfun, return`

## Formato de `obj.txt`

1. Lista de constantes: `valor  dirección`
2. Contadores de memoria por tipo (global_int, ..., cte_str)
3. Bloque de memoria requerida por cada función (dir, params, local_int, ...)
4. Cuádruplos: `num  op  argL  argR  res` (todo en direcciones; `-1` = no usado)

## Máquina virtual

- Memoria simulada con diccionarios por región (global+constantes compartidas).
- Call stack de **activation records**: cada `gosub` empuja un frame con memoria
  local/temporal propia; `endfun` hace pop y regresa al quad guardado. Esto hace
  funcionar la recursión.
- Errores de runtime (abortan ejecución): división entre cero, acceso a memoria
  virtual no reservada, profundidad de recursión > 1000.

## Plan de implementación (por etapas, con checkpoint)

1. Memoria virtual + operadores alineados → genera obj.txt y salida_debug.txt.
2. VM básica: asignación, aritmética, constantes, print/newline.
3. Control de flujo: if/else, do-while, break.
4. Funciones: sub/param/gosub/endfun + activation records + recursión.
5. Errores de runtime + integración (main.py) + casos de prueba.
