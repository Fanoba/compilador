import ply.lex as lex
import ply.yacc as yacc

# =====================================================================
# 1. ANALIZADOR LÉXICO (LEXER)
# =====================================================================

reserved = {
    'program': 'PROGRAM', 'main': 'MAIN', 'var': 'VAR', 'end': 'END',
    'int': 'INT', 'float': 'FLOAT', 'string': 'STRING', 'void': 'VOID',
    'bool': 'BOOL',
    'return': 'RETURN',
    'true': 'TRUE',
    'false': 'FALSE',
    'if': 'IF', 'else': 'ELSE', 'do': 'DO', 'while': 'WHILE', 'print': 'PRINT',
}

tokens = [
    'CTE_FLOAT', 'CTE_INT', 'CTE_STR', 'ID',
    'OP_ASSIGN', 'OP_SUM', 'OP_MINUS', 'OP_MULT', 'OP_DIV',
    'OP_GTE', 'OP_LTE', 'OP_NEQ', 'OP_EQ', 'OP_GT', 'OP_LT',
    'SEMICOLON', 'COMMA', 'COLON',
    'OPEN_PAR', 'CLOSE_PAR', 'OPEN_BRA', 'CLOSE_BRA', 'OPEN_KEY', 'CLOSE_KEY',
] + list(reserved.values())

t_OP_ASSIGN = r'='
t_OP_SUM = r'\+'
t_OP_MINUS = r'\-'
t_OP_MULT = r'\*'
t_OP_DIV = r'\/'
t_OP_GTE = r'>='
t_OP_LTE = r'<='
t_OP_NEQ = r'<>'
t_OP_EQ = r'=='
t_OP_GT = r'>'
t_OP_LT = r'<'
t_SEMICOLON = r';'
t_COMMA = r','
t_COLON = r':'
t_OPEN_PAR = r'\('
t_CLOSE_PAR = r'\)'
t_OPEN_BRA = r'\['
t_CLOSE_BRA = r'\]'
t_OPEN_KEY = r'\{'
t_CLOSE_KEY = r'\}'

t_ignore = ' \t'

def t_CTE_FLOAT(t):
    r'\d+\.\d+'
    t.value = float(t.value)
    return t

def t_CTE_INT(t):
    r'\d+'
    t.value = int(t.value)
    return t

def t_CTE_STR(t):
    r'\"([^\\\"]|\\.)*\"'
    t.value = t.value[1:-1]
    return t

def t_ID(t):
    r'[a-zA-Z][a-zA-Z0-9]*'
    t.type = reserved.get(t.value, 'ID')
    return t

def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

def t_error(t):
    print(f"❌ Error Léxico: Carácter ilegal '{t.value[0]}' en la línea {t.lexer.lineno}")
    t.lexer.skip(1)

lexer = lex.lex()

# =====================================================================
# 2. ANALIZADOR SINTÁCTICO (PARSER) & REGLAS DE GRAMÁTICA
# =====================================================================

def p_programa(p):
    '''programa : PROGRAM ID SEMICOLON variables bloque END
                | PROGRAM ID SEMICOLON bloque END'''
    print("¡Análisis sintáctico finalizado exitosamente!")

def p_variables(p):
    '''variables : VAR var_lista'''

def p_var_lista(p):
    '''var_lista : id_lista COLON tipo SEMICOLON var_lista
                 | id_lista COLON tipo SEMICOLON'''

def p_id_lista(p):
    '''id_lista : ID COMMA id_lista
                | ID'''

def p_tipo(p):
    '''tipo : INT
            | FLOAT
            | STRING
            | BOOL'''

def p_bloque(p):
    '''bloque : OPEN_KEY estatutos_reg CLOSE_KEY
              | OPEN_KEY CLOSE_KEY'''

def p_estatutos_reg(p):
    '''estatutos_reg : estatuto estatutos_reg
                     | estatuto'''

def p_estatuto(p):
    '''estatuto : asignacion
                | condicion
                | escritura
                | ciclo
                | retorno'''

def p_asignacion(p):
    '''asignacion : ID OP_ASSIGN expresion SEMICOLON'''

def p_retorno(p):
    '''retorno : RETURN expresion SEMICOLON
               | RETURN SEMICOLON'''

def p_escritura(p):
    '''escritura : PRINT OPEN_PAR expresion_lista CLOSE_PAR SEMICOLON'''

def p_expresion_lista(p):
    '''expresion_lista : expresion COMMA expresion_lista
                       | expresion
                       | CTE_STR COMMA expresion_lista
                       | CTE_STR'''

def p_condicion(p):
    '''condicion : IF OPEN_PAR expresion CLOSE_PAR bloque SEMICOLON
                 | IF OPEN_PAR expresion CLOSE_PAR bloque ELSE bloque SEMICOLON'''

def p_ciclo(p):
    '''ciclo : WHILE OPEN_PAR expresion CLOSE_PAR bloque SEMICOLON'''

def p_expresion(p):
    '''expresion : exp OP_GT exp
                 | exp OP_LT exp
                 | exp OP_NEQ exp
                 | exp OP_EQ exp
                 | exp OP_GTE exp
                 | exp OP_LTE exp
                 | exp'''

def p_exp(p):
    '''exp : termino OP_SUM exp
           | termino OP_MINUS exp
           | termino'''

def p_termino(p):
    '''termino : factor OP_MULT termino
               | factor OP_DIV termino
               | factor'''

def p_factor_par(p):
    '''factor : OPEN_PAR expresion CLOSE_PAR'''

def p_factor_signo_int(p):
    '''factor : OP_SUM CTE_INT
              | OP_MINUS CTE_INT
              | CTE_INT'''

def p_factor_signo_float(p):
    '''factor : OP_SUM CTE_FLOAT
              | OP_MINUS CTE_FLOAT
              | CTE_FLOAT'''

def p_factor_id(p):
    '''factor : ID'''

def p_factor_bool(p):
    '''factor : TRUE
              | FALSE'''

# =====================================================================
# 3. ESTRATEGIA DE RECUPERACIÓN DE ERRORES SINTÁCTICOS
# =====================================================================

def p_error(p):
    if p:
        # Obtenemos la línea exacta usando el arreglo de líneas que guardamos en el parser
        linea_codigo = "Línea no disponible"
        if hasattr(parser, 'lineas_codigo') and 0 < p.lineno <= len(parser.lineas_codigo):
            linea_codigo = parser.lineas_codigo[p.lineno - 1]
        
        # Formato de impresión solicitado por el usuario
        print(f"Línea {p.lineno} -> {linea_codigo}")
        print(f"Error de Sintaxis: Token inesperado '{p.value}' (Tipo: {p.type})")
        print("-" * 40)
        
        # Estrategia de recuperación por pánico
        while True:
            tok = parser.token()
            if not tok or tok.type in ['SEMICOLON', 'CLOSE_KEY', 'END']:
                break
        if tok:
            print(f"Parser sincronizado y recuperado en el token: '{tok.type}'. Continuando análisis...\n")
            parser.errok()
            return tok
    else:
        print("❌ Error de Sintaxis: Fin de archivo (EOF) inesperado. Estructura incompleta.")

# Construir el parser
parser = yacc.yacc()

# =====================================================================
# 4. EJECUCIÓN DIRECTA DESDE UN STRING
# =====================================================================

if __name__ == '__main__':
    codigo_input = """program programaPruebaMaestro;
var x, y : int;
    status : bool;
    %mivar : float;
{
    x = 10
    y = 15;
    
    status = true;
    
    if (x >> 5) {
        print("X es mayor")
    };
    
        while (status {
        x = x + 1;
    };

    print("Texto bien", );
    
    return ;
}
@
end"""
        
    print("\n--- [ANÁLISIS SINTÁCTICO] ---")
    
    # Dividimos el string por saltos de línea para poder extraerlas de forma individual en el p_error
    # Guardamos este arreglo directamente como un atributo dinámico del objeto parser.
    parser.lineas_codigo = codigo_input.split('\n')
    
    # Forzar el reinicio del contador de líneas del lexer antes de analizar
    lexer.lineno = 1
    
    parser.parse(codigo_input)