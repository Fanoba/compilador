# Little Duck Compiler 🦆

Compilador para el lenguaje **Little Duck** utilizando **PLY (Python Lex-Yacc)** en Python.

Este proyecto implementa un analizador léxico y sintáctico basado en gramáticas **LALR(1)** utilizando las librerías:

```python
import ply.lex as lex
import ply.yacc as yacc
```

---

## Objetivo del Proyecto

Desarrollar un compilador capaz de:

- Leer archivos `.txt` con programas escritos en Little Duck.
- Reconocer elementos léxicos mediante expresiones regulares.
- Generar un stream de tokens.
- Validar la sintaxis del lenguaje usando una gramática LR.
- Detectar y reportar errores léxicos y sintácticos.
- Recuperarse de errores y continuar el análisis del programa.

---

## Tecnologías Utilizadas

- Python 3
- PLY (Python Lex-Yacc)

---

## Estructura General

```bash
project/
│
├── compilador.py          # Analizador léxico
├── programa.txt   #Pruebas
└── README.md
```

---

## Funcionalidades

### 1. Lectura de archivos

El compilador leerá archivos `.txt` que contienen código fuente escrito en Little Duck.


### 2. Análisis Léxico

Se utilizarán expresiones regulares para identificar:

- Palabras reservadas
- Identificadores
- Operadores
- Números
- Strings
- Símbolos especiales

El resultado será un **token stream** generado con PLY.

---

### 3. Análisis Sintáctico

Se implementará una gramática utilizando `ply.yacc`.

Las reglas sintácticas se definirán mediante funciones separadas.



### 4. Manejo de Errores

El compilador deberá:

- Reportar errores léxicos
- Reportar errores sintácticos
- Mostrar:
  - Subcadena infractora
  - Línea
  - Posición


---

### 5. Recuperación de Errores

El parser no debe detenerse tras el primer error.

Se investigarán e implementarán estrategias de recuperación de errores disponibles en PLY, como:

- Uso del token especial `error`
- Sincronización por delimitadores
- Recuperación parcial del parsing

Documentación oficial:
https://www.dabeaz.com/ply/ply.html

---

## Instalación

Instalar PLY:

```bash
pip install ply
```

---

## Ejecución

Ejecutar el compilador:

```bash
python main.py
```

---

## Objetivos Académicos

Este proyecto busca reforzar conceptos de:

- Compiladores
- Gramáticas LR
- Parsing LALR(1)
- Expresiones regulares
- Manejo de errores
- Construcción de analizadores léxicos y sintácticos

---

## Autores

Proyecto académico de compiladores utilizando Python y PLY.
