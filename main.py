import ply.lex as lex
import ply.yacc as yacc
import os

# =============================================================================
# 1. PALABRAS RESERVADAS Y TOKENS
# =============================================================================
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

t_OP_SUM = r'\+'
t_OP_MINUS = r'\-'
t_OP_MULT = r'\*'
t_OP_DIV = r'\/'
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


def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)


def t_OP_GTE(t): r'>='; return t


def t_OP_LTE(t): r'<='; return t


def t_OP_NEQ(t): r'!='; return t


def t_OP_EQ(t):  r'=='; return t


def t_OP_GT(t):  r'>';  return t


def t_OP_LT(t):  r'<';  return t


def t_OP_ASSIGN(t): r'='; return t


def t_CTE_FLOAT(t):
    r'\d+\.\d+';
    t.value = float(t.value);
    return t


def t_CTE_INT(t):
    r'\d+';
    t.value = int(t.value);
    return t


def t_CTE_STR(t):
    r'\"([^\\\n]|(\\.))*?\"';
    return t


def t_ID(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*';
    t.type = reserved.get(t.value, 'ID');
    return t


def t_comment(t):
    r'\#.*';
    pass


def t_error(t):
    print(f"  [Error lexico] Simbolo no reconocido '{t.value[0]}' en posicion {t.lexpos}")
    t.lexer.skip(1)


lexer = lex.lex()

# =============================================================================
# 2. MANEJO DE ERRORES AVANZADO CORREGIDO
# =============================================================================
texto_actual = ""


def buscar_columna(input_text, token):
    line_start = input_text.rfind('\n', 0, token.lexpos) + 1
    return (token.lexpos - line_start) + 1


def p_error(p):
    global texto_actual
    if p:
        columna = buscar_columna(texto_actual, p)
        print(f"  [Error Sintactico] Token inesperado: '{p.value}' en Linea: {p.lineno}, Columna: {columna}")
        yacc.errok()
    else:
        print("  [Error Sintactico] Error fatal: Fin de archivo inesperado (EOF).")


# =============================================================================
# 3. GRAMÁTICA LR COMPLETA
# =============================================================================

def p_programa(p):
    '''programa : PROGRAM ID SEMICOLON vars_opcional funcs_opcional MAIN body END'''
    print("\n  [Sintaxis] ¡Programa estructurado correctamente siguiendo el diagrama principal!")


def p_vars_opcional_vacio(p):  '''vars_opcional : '''


def p_vars_opcional_data(p):   '''vars_opcional : vars'''


def p_funcs_opcional_vacio(p): '''funcs_opcional : '''


def p_funcs_opcional_data(p):  '''funcs_opcional : funcs'''


def p_vars(p):
    '''vars : VAR lista_ids COLON tipo SEMICOLON'''
    pass


def p_lista_ids_single(p):   '''lista_ids : ID'''


def p_lista_ids_multiple(p): '''lista_ids : ID COMMA lista_ids'''


def p_tipo_int(p):    '''tipo : INT'''


def p_tipo_float(p):  '''tipo : FLOAT'''


def p_tipo_string(p): '''tipo : STRING'''


def p_tipo_bool(p):   '''tipo : BOOL'''


def p_tipo_void(p):   '''tipo : VOID'''


def p_funcs_single(p):
    '''funcs : funcion funcs'''
    pass


def p_funcs_end(p):
    '''funcs : funcion'''
    pass


def p_funcion(p):
    '''funcion : tipo ID OPEN_PAR parametros_opc CLOSE_PAR OPEN_BRA vars_opcional body CLOSE_BRA SEMICOLON'''
    pass


def p_parametros_opc_vacio(p): '''parametros_opc : '''


def p_parametros_opc_data(p):  '''parametros_opc : lista_parametros'''


def p_lista_parametros_single(p):   '''lista_parametros : ID COLON tipo'''


def p_lista_parametros_multiple(p): '''lista_parametros : ID COLON tipo COMMA lista_parametros'''


def p_body(p):
    '''body : OPEN_KEY lista_statements CLOSE_KEY'''
    pass


def p_lista_statements_vacio(p): '''lista_statements : '''


def p_lista_statements_data(p):  '''lista_statements : statement lista_statements'''


def p_statement_assign(p):    '''statement : assign'''


def p_statement_condition(p): '''statement : condition'''


def p_statement_cycle(p):     '''statement : cycle'''


def p_statement_f_call(p):    '''statement : f_call'''


def p_statement_print(p):     '''statement : print'''


def p_statement_return(p):    '''statement : return_stmt'''


def p_statement_error(p):     '''statement : error SEMICOLON'''


def p_assign(p):
    '''assign : ID OP_ASSIGN expresion SEMICOLON'''
    pass


def p_print(p):
    '''print : PRINT OPEN_PAR contenido_print CLOSE_PAR SEMICOLON'''
    pass


def p_contenido_print_single(p):   '''contenido_print : expresion'''


def p_contenido_print_multiple(p): '''contenido_print : expresion COMMA contenido_print'''


def p_cycle(p):
    '''cycle : DO body WHILE OPEN_PAR expresion CLOSE_PAR SEMICOLON'''
    pass


def p_condition_if(p):
    '''condition : IF OPEN_PAR expresion CLOSE_PAR body SEMICOLON'''
    pass


def p_condition_if_else(p):
    '''condition : IF OPEN_PAR expresion CLOSE_PAR body ELSE body SEMICOLON'''
    pass


def p_f_call(p):
    '''f_call : ID OPEN_PAR argumentos_opc CLOSE_PAR SEMICOLON'''
    pass


def p_argumentos_opc_vacio(p): '''argumentos_opc : '''


def p_argumentos_opc_data(p):  '''argumentos_opc : lista_expresiones'''


def p_lista_expresiones_single(p):   '''lista_expresiones : expresion'''


def p_lista_expresiones_multiple(p): '''lista_expresiones : expresion COMMA lista_expresiones'''


def p_return_stmt_val(p):   '''return_stmt : RETURN expresion SEMICOLON'''


def p_return_stmt_empty(p): '''return_stmt : RETURN SEMICOLON'''


# --- INFRAESTRUCTURA DE EXPRESIONES ---
def p_expresion_rel(p):    '''expresion : exp rel_op exp'''


def p_expresion_simple(p): '''expresion : exp'''


def p_rel_op_gt(p):  '''rel_op : OP_GT'''


def p_rel_op_lt(p):  '''rel_op : OP_LT'''


def p_rel_op_gte(p): '''rel_op : OP_GTE'''


def p_rel_op_lte(p): '''rel_op : OP_LTE'''


def p_rel_op_neq(p): '''rel_op : OP_NEQ'''


def p_rel_op_eq(p):  '''rel_op : OP_EQ'''


def p_exp_sum(p):    '''exp : exp OP_SUM termino'''


def p_exp_minus(p):  '''exp : exp OP_MINUS termino'''


def p_exp_term(p):   '''exp : termino'''


def p_termino_mult(p): '''termino : termino OP_MULT factor'''


def p_termino_div(p):  '''termino : termino OP_DIV factor'''


def p_termino_fact(p): '''termino : factor'''


def p_factor_nested(p):    '''factor : OPEN_PAR expresion CLOSE_PAR'''


def p_factor_unary_sum(p):  '''factor : OP_SUM base'''


def p_factor_unary_min(p):  '''factor : OP_MINUS base'''


def p_factor_base(p):       '''factor : base'''


def p_factor_id(p):         '''factor : ID'''


# SOLUCIÓN AL ERROR SINTÁCTICO: Permitir llamadas a funciones sin punto y coma como factores válidos
def p_factor_f_call(p):     '''factor : ID OPEN_PAR argumentos_opc CLOSE_PAR'''


pass


def p_base_cte_int(p):   '''base : CTE_INT'''


def p_base_cte_float(p): '''base : CTE_FLOAT'''


def p_base_cte_str(p):   '''base : CTE_STR'''


def p_base_true(p):      '''base : TRUE'''


def p_base_false(p):     '''base : FALSE'''


parser = yacc.yacc()

# =============================================================================
# 4. EJECUCIÓN DESDE EL ARCHIVO
# =============================================================================
nombre_archivo = "programa.txt"

if __name__ == '__main__':
    print("=" * 70)
    print("PROBANDO GRAMÁTICA LR CON RECURSIVIDAD COMPLETA")
    print("=" * 70)

    if os.path.exists(nombre_archivo):
        with open(nombre_archivo, "r", encoding="utf-8") as f:
            texto_actual = f.read()

        print(f"[OK] Leyendo contenido de '{nombre_archivo}'...")
        print("-" * 40)
        print(texto_actual)
        print("-" * 40)

        # Correr el analizador
        parser.parse(texto_actual, lexer=lexer)
    else:
        print(f"[!] Archivo '{nombre_archivo}' no encontrado. Por favor crealo con tu codigo de Fibonacci.")