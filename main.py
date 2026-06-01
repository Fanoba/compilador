import ply.lex as lex
import ply.yacc as yacc

# =============================================================================
# 0. ESTRUCTURAS DE DATOS SEMÁNTICAS
# =============================================================================

# --- Tipos de datos ---
T_INT = 'int'
T_FLOAT = 'float'
T_STRING = 'string'
T_BOOL = 'bool'
T_VOID = 'void'
T_ERROR = 'error'


# --- Cuádruplo ---
class Quadruple:
    def __init__(self, op, arg1, arg2, res, type_res=None):
        self.op = op
        self.arg1 = arg1
        self.arg2 = arg2
        self.res = res
        self.type_res = type_res if type_res is not None else '-'

    def as_tuple(self):
        return (self.op, self.arg1, self.arg2, self.res, self.type_res)


# --- Cubo Semántico ---
class SemanticCube:
    def __init__(self):
        self.cube = {}
        arith = ['+', '-', '*', '/']
        rel_eq = ['==', '!=']
        rel_ord = ['>', '<', '>=', '<=']

        for op in arith:
            self.cube[(op, T_INT, T_INT)] = T_INT
            self.cube[(op, T_FLOAT, T_FLOAT)] = T_FLOAT
            self.cube[(op, T_INT, T_FLOAT)] = T_FLOAT
            self.cube[(op, T_FLOAT, T_INT)] = T_FLOAT

        for op in rel_eq + rel_ord:
            self.cube[(op, T_INT, T_INT)] = T_BOOL
            self.cube[(op, T_FLOAT, T_FLOAT)] = T_BOOL
            self.cube[(op, T_INT, T_FLOAT)] = T_BOOL
            self.cube[(op, T_FLOAT, T_INT)] = T_BOOL

        # Igualdad/desigualdad para strings
        for op in rel_eq:
            self.cube[(op, T_STRING, T_STRING)] = T_BOOL

        # Asignación: usa misma matriz, validamos compatibilidad
        self.cube[('=', T_INT, T_INT)] = T_INT
        self.cube[('=', T_FLOAT, T_FLOAT)] = T_FLOAT
        self.cube[('=', T_FLOAT, T_INT)] = T_FLOAT
        self.cube[('=', T_STRING, T_STRING)] = T_STRING

    def query(self, op, t1, t2):
        return self.cube.get((op, t1, t2), T_ERROR)


# --- Tabla de variables ---
class VariableTable:
    def __init__(self):
        self.vars = {}

    def add(self, name, var_type):
        if name in self.vars:
            return False
        self.vars[name] = {'type': var_type}
        return True

    def get(self, name):
        return self.vars.get(name)

    def exists(self, name):
        return name in self.vars


# --- Directorio de funciones ---
class FunctionDirectory:
    def __init__(self):
        self.funcs = {}

    def add(self, name, return_type, params=None):
        if name in self.funcs:
            return False
        self.funcs[name] = {
            'return_type': return_type,
            'params': params if params else [],
            'var_table': VariableTable(),
            'num_params': 0,
            'num_vars': 0,
            'quad_start': None,
        }
        return True

    def get(self, name):
        return self.funcs.get(name)

    def exists(self, name):
        return name in self.funcs


# --- Manager Semántico (estado central) ---
class SemanticManager:
    def __init__(self):
        self.func_dir = FunctionDirectory()
        self.cube = SemanticCube()
        self.quads = []
        self.operand_stack = []
        self.operator_stack = []
        self.type_stack = []
        self.jump_stack = []
        self.break_stack = []  # pila de pilas: una lista de saltos por cada ciclo
        self.temp_counter = 0
        self.current_scope = 'global'
        self.current_func = None
        self.has_errors = False
        # Para validar parámetros en llamadas
        self.call_stack = []     # nombre de función siendo llamada
        self.arg_counter = []    # índice de argumento actual en cada llamada

    # --- Helpers de error ---
    def error(self, msg):
        self.has_errors = True
        print(f"  [Error Semantico] {msg}")

    # --- Temporales y quads ---
    def new_temp(self):
        self.temp_counter += 1
        return f"t{self.temp_counter}"

    def emit(self, op, arg1, arg2, res, type_res='-'):
        self.quads.append(Quadruple(op, arg1, arg2, res, type_res))
        return len(self.quads)  # índice 1-based del quad recién emitido

    def fill(self, idx, value):
        # idx es 1-based; convertimos a 0-based al indexar
        self.quads[idx - 1].res = value

    # --- Variables / scopes ---
    def declare_var(self, name, var_type):
        scope = self.current_scope
        func_info = self.func_dir.get(scope)
        if func_info is None:
            self.error(f"Scope '{scope}' no existe al declarar '{name}'")
            return
        if not func_info['var_table'].add(name, var_type):
            self.error(f"Variable '{name}' ya declarada en scope '{scope}'")
        else:
            func_info['num_vars'] += 1

    def lookup_var(self, name):
        # Busca primero en scope local, luego en global
        local = self.func_dir.get(self.current_scope)
        if local and local['var_table'].exists(name):
            return local['var_table'].get(name), self.current_scope
        glob = self.func_dir.get('global')
        if glob and glob['var_table'].exists(name):
            return glob['var_table'].get(name), 'global'
        return None, None


# Instancia global del manager
sm = SemanticManager()

# =============================================================================
# 1. PALABRAS RESERVADAS Y TOKENS
# =============================================================================
reserved = {
    'program': 'PROGRAM', 'main': 'MAIN', 'var': 'VAR', 'end': 'END',
    'int': 'INT', 'float': 'FLOAT', 'string': 'STRING', 'void': 'VOID',
    'return': 'RETURN',
    'break': 'BREAK',
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
hubo_errores = False  # VARIABLE AGREGADA PARA CONTROLAR EL MENSAJE FALSO


def buscar_columna(input_text, token):
    line_start = input_text.rfind('\n', 0, token.lexpos) + 1
    return (token.lexpos - line_start) + 1


def p_error(p):
    global texto_actual, hubo_errores
    hubo_errores = True  # ACTIVAMOS LA ALARMA DE ERRORES
    
    if p:
        columna = buscar_columna(texto_actual, p)
        print(f"  [Error Sintactico] Token inesperado: '{p.value}' en Linea: {p.lineno}, Columna: {columna}")
        
        # Opcional: Sugerencias predictivas
        try:
            estado_actual = parser.statestack[-1]
            tokens_esperados = list(parser.action[estado_actual].keys())
            esperados_limpios = [tok for tok in tokens_esperados if tok not in ('$end', 'error')]
            if esperados_limpios:
                esperados_str = ", ".join(esperados_limpios)
                print(f"  [Sugerencia] El compilador esperaba recibir: {esperados_str}")
        except:
            pass
            
        parser.errok()
    else:
        print("  [Error Sintactico] Error fatal: Fin de archivo inesperado (EOF).")


# =============================================================================
# 3. GRAMÁTICA LR COMPLETA
# =============================================================================

def p_programa(p):
    '''programa : PROGRAM ID np_prog_start SEMICOLON vars_opcional funcs_opcional MAIN np_main_start body END'''
    global hubo_errores
    if not hubo_errores and not sm.has_errors:
        print("\n  [Sintaxis] ¡Programa estructurado correctamente siguiendo el diagrama principal!")
    elif hubo_errores:
        print("\n  [Sintaxis] El análisis terminó, pero se encontraron errores sintácticos. Revisa los mensajes arriba.")
    # Quad final
    sm.emit('END', None, None, None, '-')


def p_np_prog_start(p):
    '''np_prog_start :'''
    sm.func_dir.add('global', T_VOID)
    sm.current_scope = 'global'
    # Quad inicial: GOTO al main (se rellena en np_main_start)
    sm.emit('GOTO', None, None, None, '-')
    sm.main_jump_idx = len(sm.quads)


def p_np_main_start(p):
    '''np_main_start :'''
    # El próximo quad será el primero de main
    sm.fill(sm.main_jump_idx, len(sm.quads) + 1)
    sm.current_scope = 'global'


def p_vars_opcional_vacio(p):  '''vars_opcional : '''
def p_vars_opcional_data(p):   '''vars_opcional : vars'''
def p_funcs_opcional_vacio(p): '''funcs_opcional : '''
def p_funcs_opcional_data(p):  '''funcs_opcional : funcs'''

# --- CORRECCIÓN: SOPORTE PARA MÚLTIPLES DECLARACIONES EN UN BLOQUE VAR ---
def p_vars(p):
    '''vars : VAR lista_declaraciones'''
    pass

def p_lista_declaraciones_single(p):
    '''lista_declaraciones : declaracion_var'''
    pass

def p_lista_declaraciones_multiple(p):
    '''lista_declaraciones : declaracion_var lista_declaraciones'''
    pass

def p_declaracion_var(p):
    '''declaracion_var : lista_ids COLON tipo SEMICOLON'''
    if p[3] == T_VOID:
        sm.error(f"No se pueden declarar variables de tipo 'void': {p[1]}")
        return
    for id_name in p[1]:
        sm.declare_var(id_name, p[3])
# -------------------------------------------------------------------------


def p_lista_ids_single(p):
    '''lista_ids : ID'''
    p[0] = [p[1]]

def p_lista_ids_multiple(p):
    '''lista_ids : ID COMMA lista_ids'''
    p[0] = [p[1]] + p[3]

def p_tipo_int(p):
    '''tipo : INT'''
    p[0] = T_INT

def p_tipo_float(p):
    '''tipo : FLOAT'''
    p[0] = T_FLOAT

def p_tipo_string(p):
    '''tipo : STRING'''
    p[0] = T_STRING

def p_tipo_void(p):
    '''tipo : VOID'''
    p[0] = T_VOID

def p_funcs_single(p):
    '''funcs : funcion funcs'''
    pass

def p_funcs_end(p):
    '''funcs : funcion'''
    pass

def p_funcion(p):
    '''funcion : tipo ID np_func_start OPEN_PAR parametros_opc CLOSE_PAR OPEN_BRA vars_opcional np_func_body body CLOSE_BRA np_func_end SEMICOLON'''
    pass


def p_np_func_start(p):
    '''np_func_start :'''
    return_type = p[-2]
    name = p[-1]
    if not sm.func_dir.add(name, return_type):
        sm.error(f"Función '{name}' ya declarada")
    sm.current_scope = name
    # Si tiene retorno no-void, registrar una variable global con el nombre de la función
    if return_type != T_VOID:
        glob = sm.func_dir.get('global')
        if glob and not glob['var_table'].exists(name):
            glob['var_table'].add(name, return_type)


def p_np_func_body(p):
    '''np_func_body :'''
    f = sm.func_dir.get(sm.current_scope)
    if f:
        f['quad_start'] = len(sm.quads) + 1


def p_np_func_end(p):
    '''np_func_end :'''
    # Verificar que las funciones no-void hayan retornado al menos un valor.
    f = sm.func_dir.get(sm.current_scope)
    if f and f['return_type'] != T_VOID and not _function_has_return(f):
        sm.error(f"Función '{sm.current_scope}' tipo '{f['return_type']}' no tiene 'return' con valor")
    sm.emit('ENDFUNC', None, None, None, '-')
    sm.current_scope = 'global'


def _function_has_return(f):
    start = f.get('quad_start', 1) - 1  # 0-based
    for q in sm.quads[start:]:
        if q.op == 'RETURN':
            return True
    return False


def p_parametros_opc_vacio(p): '''parametros_opc : '''
def p_parametros_opc_data(p):  '''parametros_opc : lista_parametros'''

def p_lista_parametros_single(p):
    '''lista_parametros : ID COLON tipo'''
    _register_param(p[1], p[3])

def p_lista_parametros_multiple(p):
    '''lista_parametros : lista_parametros COMMA ID COLON tipo'''
    _register_param(p[3], p[5])


def _register_param(name, ptype):
    if ptype == T_VOID:
        sm.error(f"El parámetro '{name}' no puede ser de tipo 'void'")
        return
    func_info = sm.func_dir.get(sm.current_scope)
    if func_info is None:
        return
    if not func_info['var_table'].add(name, ptype):
        sm.error(f"Parámetro '{name}' duplicado en función '{sm.current_scope}'")
        return
    func_info['params'].append((name, ptype))
    func_info['num_params'] += 1
    func_info['num_vars'] += 1

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
def p_statement_break(p):
    '''statement : BREAK SEMICOLON'''
    if not sm.break_stack:
        sm.error("'break' fuera de un ciclo")
        return
    sm.emit('GOTO', None, None, None, '-')
    sm.break_stack[-1].append(len(sm.quads))
def p_statement_error(p):     '''statement : error SEMICOLON'''

def p_assign(p):
    '''assign : ID OP_ASSIGN expresion SEMICOLON'''
    if not sm.operand_stack:
        return
    val = sm.operand_stack.pop()
    tval = sm.type_stack.pop()
    var, _ = sm.lookup_var(p[1])
    if var is None:
        sm.error(f"Variable '{p[1]}' no declarada (en asignación)")
        return
    res_type = sm.cube.query('=', var['type'], tval)
    if res_type == T_ERROR:
        sm.error(f"No se puede asignar '{tval}' a '{p[1]}' ({var['type']})")
        return
    sm.emit('=', val, None, p[1], var['type'])

def p_print(p):
    '''print : PRINT OPEN_PAR contenido_print CLOSE_PAR SEMICOLON'''
    pass

def p_contenido_print_single(p):
    '''contenido_print : expresion np_print_item'''
    pass

def p_contenido_print_multiple(p):
    '''contenido_print : expresion np_print_item COMMA contenido_print'''
    pass

def p_np_print_item(p):
    '''np_print_item :'''
    if not sm.operand_stack:
        return
    val = sm.operand_stack.pop()
    sm.type_stack.pop()
    sm.emit('PRINT', None, None, val, '-')

def p_cycle(p):
    '''cycle : DO np_cycle_start body WHILE OPEN_PAR expresion CLOSE_PAR np_cycle_end SEMICOLON'''
    pass

def p_np_cycle_start(p):
    '''np_cycle_start :'''
    # Marca inicio del ciclo (próximo quad). Usamos 1-based.
    sm.jump_stack.append(len(sm.quads) + 1)
    sm.break_stack.append([])

def p_np_cycle_end(p):
    '''np_cycle_end :'''
    if not sm.type_stack:
        sm.break_stack.pop() if sm.break_stack else None
        sm.jump_stack.pop() if sm.jump_stack else None
        return
    t = sm.type_stack.pop()
    val = sm.operand_stack.pop()
    if t != T_BOOL:
        sm.error(f"La condición del while debe ser booleana, se recibió '{t}'")
    start = sm.jump_stack.pop()
    sm.emit('GOTOT', val, None, start, '-')
    # Resolver los breaks: deben saltar al quad que viene después del GOTOT
    target = len(sm.quads) + 1
    for b_idx in sm.break_stack.pop():
        sm.fill(b_idx, target)


def p_condition_if(p):
    '''condition : IF OPEN_PAR expresion np_if_cond CLOSE_PAR body np_if_end SEMICOLON'''
    pass

def p_condition_if_else(p):
    '''condition : IF OPEN_PAR expresion np_if_cond CLOSE_PAR body np_if_else ELSE body np_if_end SEMICOLON'''
    pass

def p_np_if_cond(p):
    '''np_if_cond :'''
    # Después de evaluar la condición: validar bool y emitir GOTOF pendiente.
    if not sm.type_stack:
        return
    t = sm.type_stack.pop()
    val = sm.operand_stack.pop()
    if t != T_BOOL:
        sm.error(f"La condición del if debe ser booleana, se recibió '{t}'")
    sm.emit('GOTOF', val, None, None, '-')
    sm.jump_stack.append(len(sm.quads))  # índice 1-based del GOTOF recién emitido

def p_np_if_else(p):
    '''np_if_else :'''
    # Antes del else: emitir GOTO al fin, y rellenar el GOTOF anterior con el inicio del else.
    sm.emit('GOTO', None, None, None, '-')
    goto_idx = len(sm.quads)
    if sm.jump_stack:
        gotof_idx = sm.jump_stack.pop()
        sm.fill(gotof_idx, len(sm.quads) + 1)
    sm.jump_stack.append(goto_idx)

def p_np_if_end(p):
    '''np_if_end :'''
    # Rellena el último salto pendiente con la posición siguiente.
    if sm.jump_stack:
        idx = sm.jump_stack.pop()
        sm.fill(idx, len(sm.quads) + 1)

def p_f_call(p):
    '''f_call : ID np_call_start OPEN_PAR argumentos_opc CLOSE_PAR SEMICOLON'''
    _call_end(p[1], as_expression=False)


def p_np_call_start(p):
    '''np_call_start :'''
    name = p[-1]
    if not sm.func_dir.exists(name):
        sm.error(f"Función '{name}' no declarada (en llamada)")
        sm.call_stack.append(None)
        sm.arg_counter.append(0)
        return
    sm.emit('ERA', None, None, name, '-')
    sm.call_stack.append(name)
    sm.arg_counter.append(0)


def _call_end(name, as_expression):
    arg_count = sm.arg_counter.pop() if sm.arg_counter else 0
    func_in_stack = sm.call_stack.pop() if sm.call_stack else None
    if func_in_stack is None:
        # Función no existía; empujar placeholder para no romper expresión
        if as_expression:
            sm.operand_stack.append('_err_')
            sm.type_stack.append(T_ERROR)
        return
    f = sm.func_dir.get(name)
    expected = len(f['params'])
    if arg_count != expected:
        sm.error(f"Función '{name}' espera {expected} argumento(s), recibió {arg_count}")
    target = f.get('quad_start') if f.get('quad_start') is not None else name
    sm.emit('GOSUB', name, None, target, '-')
    if as_expression:
        if f['return_type'] == T_VOID:
            sm.error(f"Función '{name}' es void y no puede usarse en expresión")
            sm.operand_stack.append('_err_')
            sm.type_stack.append(T_ERROR)
            return
        # El valor de retorno está en la variable global con el mismo nombre de la función
        temp = sm.new_temp()
        sm.emit('=', name, None, temp, f['return_type'])
        sm.operand_stack.append(temp)
        sm.type_stack.append(f['return_type'])

def p_argumentos_opc_vacio(p): '''argumentos_opc : '''
def p_argumentos_opc_data(p):  '''argumentos_opc : lista_expresiones'''

def p_lista_expresiones_single(p):
    '''lista_expresiones : expresion np_call_arg'''

def p_lista_expresiones_multiple(p):
    '''lista_expresiones : expresion np_call_arg COMMA lista_expresiones'''

def p_np_call_arg(p):
    '''np_call_arg :'''
    if not sm.operand_stack or not sm.type_stack:
        return
    val = sm.operand_stack.pop()
    tval = sm.type_stack.pop()
    func_name = sm.call_stack[-1] if sm.call_stack else None
    idx = sm.arg_counter[-1] if sm.arg_counter else 0
    if func_name is not None:
        f = sm.func_dir.get(func_name)
        if f and idx < len(f['params']):
            pname, ptype = f['params'][idx]
            ok = sm.cube.query('=', ptype, tval)
            if ok == T_ERROR:
                sm.error(
                    f"Argumento {idx+1} de '{func_name}': tipo '{tval}' "
                    f"incompatible con parámetro '{pname}' ({ptype})"
                )
        sm.emit('PARAM', val, None, f"par{idx+1}", '-')
    if sm.arg_counter:
        sm.arg_counter[-1] += 1

def p_return_stmt_val(p):
    '''return_stmt : RETURN expresion SEMICOLON'''
    if not sm.operand_stack:
        return
    val = sm.operand_stack.pop()
    tval = sm.type_stack.pop()
    if sm.current_scope == 'global':
        sm.error("'return' fuera de una función")
        return
    f = sm.func_dir.get(sm.current_scope)
    if f['return_type'] == T_VOID:
        sm.error(f"Función '{sm.current_scope}' es void y no debe retornar un valor")
        return
    res = sm.cube.query('=', f['return_type'], tval)
    if res == T_ERROR:
        sm.error(
            f"Tipo de retorno '{tval}' incompatible con tipo declarado "
            f"'{f['return_type']}' en función '{sm.current_scope}'"
        )
        return
    sm.emit('=', val, None, sm.current_scope, f['return_type'])
    sm.emit('RETURN', None, None, None, '-')


def p_return_stmt_empty(p):
    '''return_stmt : RETURN SEMICOLON'''
    if sm.current_scope == 'global':
        sm.error("'return' fuera de una función")
        return
    f = sm.func_dir.get(sm.current_scope)
    if f['return_type'] != T_VOID:
        sm.error(
            f"Función '{sm.current_scope}' tipo '{f['return_type']}' "
            f"debe retornar un valor"
        )
        return
    sm.emit('RETURN', None, None, None, '-')


# --- INFRAESTRUCTURA DE EXPRESIONES ---
def p_expresion_rel(p):
    '''expresion : exp rel_op exp'''
    _reduce_binop(p[2])

def p_expresion_simple(p):
    '''expresion : exp'''
    pass

def p_rel_op_gt(p):  '''rel_op : OP_GT''';  p[0] = '>'
def p_rel_op_lt(p):  '''rel_op : OP_LT''';  p[0] = '<'
def p_rel_op_gte(p): '''rel_op : OP_GTE'''; p[0] = '>='
def p_rel_op_lte(p): '''rel_op : OP_LTE'''; p[0] = '<='
def p_rel_op_neq(p): '''rel_op : OP_NEQ'''; p[0] = '!='
def p_rel_op_eq(p):  '''rel_op : OP_EQ''';  p[0] = '=='

def p_exp_sum(p):
    '''exp : exp OP_SUM termino'''
    _reduce_binop('+')

def p_exp_minus(p):
    '''exp : exp OP_MINUS termino'''
    _reduce_binop('-')

def p_exp_term(p):
    '''exp : termino'''
    pass

def p_termino_mult(p):
    '''termino : termino OP_MULT factor'''
    _reduce_binop('*')

def p_termino_div(p):
    '''termino : termino OP_DIV factor'''
    _reduce_binop('/')

def p_termino_fact(p):
    '''termino : factor'''
    pass


def _reduce_binop(op):
    """Pop dos operandos, valida tipos con el cubo, genera quad, empuja temp."""
    if len(sm.operand_stack) < 2:
        return
    right = sm.operand_stack.pop()
    t_right = sm.type_stack.pop()
    left = sm.operand_stack.pop()
    t_left = sm.type_stack.pop()
    res_type = sm.cube.query(op, t_left, t_right)
    if res_type == T_ERROR:
        sm.error(f"Tipos incompatibles para '{op}': {t_left} vs {t_right}")
        sm.operand_stack.append('_err_')
        sm.type_stack.append(T_ERROR)
        return
    temp = sm.new_temp()
    sm.emit(op, left, right, temp, res_type)
    sm.operand_stack.append(temp)
    sm.type_stack.append(res_type)


# --- OPERACIONES UNARIAS APLICADAS AL FACTOR (FUNCIONES/VARIABLES) ---
def p_factor_nested(p):
    '''factor : OPEN_PAR expresion CLOSE_PAR'''
    pass

def p_factor_unary_sum(p):
    '''factor : OP_SUM factor'''
    pass  # +x es identidad

def p_factor_unary_min(p):
    '''factor : OP_MINUS factor'''
    if not sm.operand_stack:
        return
    val = sm.operand_stack.pop()
    tval = sm.type_stack.pop()
    res_type = sm.cube.query('-', T_INT, tval)
    if res_type == T_ERROR:
        sm.error(f"Operador unario '-' no aplica a tipo '{tval}'")
        sm.operand_stack.append('_err_')
        sm.type_stack.append(T_ERROR)
        return
    temp = sm.new_temp()
    sm.emit('-', 0, val, temp, res_type)
    sm.operand_stack.append(temp)
    sm.type_stack.append(res_type)

def p_factor_base(p):
    '''factor : base'''
    pass
def p_factor_id(p):
    '''factor : ID'''
    var, _ = sm.lookup_var(p[1])
    if var is None:
        sm.error(f"Variable '{p[1]}' no declarada (en expresión)")
        sm.operand_stack.append(p[1])
        sm.type_stack.append(T_ERROR)
    else:
        sm.operand_stack.append(p[1])
        sm.type_stack.append(var['type'])

def p_factor_f_call(p):
    '''factor : ID np_call_start OPEN_PAR argumentos_opc CLOSE_PAR'''
    _call_end(p[1], as_expression=True)
# ---------------------------------------------------------------------------------

def p_base_cte_int(p):
    '''base : CTE_INT'''
    sm.operand_stack.append(p[1])
    sm.type_stack.append(T_INT)

def p_base_cte_float(p):
    '''base : CTE_FLOAT'''
    sm.operand_stack.append(p[1])
    sm.type_stack.append(T_FLOAT)

def p_base_cte_str(p):
    '''base : CTE_STR'''
    sm.operand_stack.append(p[1])
    sm.type_stack.append(T_STRING)

parser = yacc.yacc()

# =============================================================================
# 4. EJECUCIÓN DESDE EL ARCHIVO
# =============================================================================

def _format_cell(v):
    return '_' if v is None else str(v)


def format_quads(quads):
    lines = []
    header = f"{'#':>4} | {'OP':<8} | {'ARG1':<14} | {'ARG2':<14} | {'RES':<14} | TIPO"
    lines.append(header)
    lines.append("-" * len(header))
    for i, q in enumerate(quads, start=1):
        lines.append(
            f"{i:>4} | {q.op:<8} | "
            f"{_format_cell(q.arg1):<14} | "
            f"{_format_cell(q.arg2):<14} | "
            f"{_format_cell(q.res):<14} | "
            f"{q.type_res}"
        )
    return "\n".join(lines)


def format_symbol_table(func_dir):
    lines = []
    lines.append("=" * 70)
    lines.append("TABLA DE SÍMBOLOS")
    lines.append("=" * 70)

    glob = func_dir.get('global')
    if glob:
        lines.append("\n[Scope: global]")
        if not glob['var_table'].vars:
            lines.append("  (sin variables)")
        for name, info in glob['var_table'].vars.items():
            lines.append(f"  - {name}: {info['type']}")

    lines.append("\n[Directorio de funciones]")
    user_funcs = {n: f for n, f in func_dir.funcs.items() if n != 'global'}
    if not user_funcs:
        lines.append("  (sin funciones de usuario)")
    for fname, finfo in user_funcs.items():
        params_str = ", ".join(f"{n}:{t}" for n, t in finfo['params']) or "(sin parámetros)"
        lines.append(
            f"  - {fname}({params_str}) -> {finfo['return_type']}  "
            f"[inicio quad: {finfo.get('quad_start', '-')}, "
            f"params: {finfo['num_params']}, vars: {finfo['num_vars']}]"
        )
        lines.append(f"      Variables locales:")
        if not finfo['var_table'].vars:
            lines.append("        (ninguna)")
        for name, info in finfo['var_table'].vars.items():
            lines.append(f"        - {name}: {info['type']}")
    return "\n".join(lines)


if __name__ == '__main__':
    print("=" * 70)
    print("COMPILADOR LITTLE DUCK - ENTREGA 2")
    print("=" * 70)

    input = open("prueba.txt").read()
    texto_actual = input

    print("[OK] Leyendo contenido de 'prueba.txt'...")
    print("-" * 40)
    print(texto_actual)
    print("-" * 40)

    parser.parse(texto_actual, lexer=lexer)

    if hubo_errores or sm.has_errors:
        print("\n[!] Hubo errores. No se generó el archivo de salida.")
    else:
        print("\n" + "=" * 70)
        print("REPRESENTACIÓN INTERMEDIA (CUÁDRUPLOS)")
        print("=" * 70)
        quads_str = format_quads(sm.quads)
        print(quads_str)

        symbols_str = format_symbol_table(sm.func_dir)
        print("\n" + symbols_str)

        # Escribir archivo de salida
        with open("prueba-ir.txt", "w", encoding="utf-8") as fout:
            fout.write(quads_str)
            fout.write("\n\n")
            fout.write(symbols_str)
            fout.write("\n")
        print("\n[OK] Representación intermedia escrita en 'prueba-ir.txt'")