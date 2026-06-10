import ply.lex as lex
import ply.yacc as yacc
import sys
# --- 0. ESTRUCTURAS DE DATOS SEMANTICAS ---

# --- Tipos de datos ---
T_INT = 'int'
T_FLOAT = 'float'
T_STRING = 'string'
T_BOOL = 'bool'
T_VOID = 'void'
T_ERROR = 'error'


# --- Cuadruplo ---
class Quadruple:
    def __init__(self, op, arg1, arg2, res, type_res=None):
        self.op = op
        self.arg1 = arg1
        self.arg2 = arg2
        self.res = res
        self.type_res = type_res if type_res is not None else '-'
        # Nombres legibles (se llenan en emit, para salida_debug.txt) (E3)
        self.arg1_name = arg1
        self.arg2_name = arg2
        self.res_name = res

    def as_tuple(self):
        return (self.op, self.arg1, self.arg2, self.res, self.type_res)


# --- Cubo Semantico ---
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

        for op in rel_eq:
            self.cube[(op, T_STRING, T_STRING)] = T_BOOL

        self.cube[('=', T_INT, T_INT)] = T_INT
        self.cube[('=', T_FLOAT, T_FLOAT)] = T_FLOAT
        self.cube[('=', T_FLOAT, T_INT)] = T_FLOAT
        self.cube[('=', T_STRING, T_STRING)] = T_STRING

    def query(self, op, t1, t2):
        return self.cube.get((op, t1, t2), T_ERROR)


# --- Administrador de Memoria Virtual (ENTREGA 3) ---
# Convencion vista en clase: cada region/tipo arranca en una direccion base.
# Global y constantes son memoria global unica. Locales y temporales se cuentan
# POR FUNCION, porque en la VM cada llamada tendra su propio frame.
class MemoryManager:
    BASE = {
        ('global', 'int'): 1000, ('global', 'float'): 2000,
        ('global', 'string'): 3000, ('global', 'void'): 4000,
        ('local', 'int'): 7000, ('local', 'float'): 8000, ('local', 'string'): 9000,
        ('temp', 'int'): 12000, ('temp', 'float'): 13000, ('temp', 'bool'): 14000,
        ('const', 'int'): 17000, ('const', 'float'): 18000, ('const', 'string'): 19000,
    }
    LIMIT = 1000  # casillas por bloque de tipo

    def __init__(self):
        self.global_count = {'int': 0, 'float': 0, 'string': 0, 'void': 0}
        self.const_count = {'int': 0, 'float': 0, 'string': 0}
        self.const_table = {}  # (valor, tipo) -> direccion
        self.local_count = {'int': 0, 'float': 0, 'string': 0}
        self.temp_count = {'int': 0, 'float': 0, 'bool': 0}

    def _alloc(self, seg, t, counter):
        offset = counter[t]
        if offset >= self.LIMIT:
            raise MemoryError(f"Memoria virtual agotada en region {seg}_{t}")
        counter[t] += 1
        return self.BASE[(seg, t)] + offset

    def new_global(self, t):
        return self._alloc('global', t, self.global_count)

    def new_local(self, t):
        return self._alloc('local', t, self.local_count)

    def new_temp(self, t):
        return self._alloc('temp', t, self.temp_count)

    def new_const(self, value, t):
        key = (value, t)
        if key in self.const_table:
            return self.const_table[key]
        addr = self._alloc('const', t, self.const_count)
        self.const_table[key] = addr
        return addr

    def reset_frame(self):
        # nuevo frame (funcion o main): locales y temporales arrancan limpias
        self.local_count = {'int': 0, 'float': 0, 'string': 0}
        self.temp_count = {'int': 0, 'float': 0, 'bool': 0}

    def snapshot_frame(self):
        return {
            'local_int': self.local_count['int'],
            'local_float': self.local_count['float'],
            'local_str': self.local_count['string'],
            'temp_int': self.temp_count['int'],
            'temp_float': self.temp_count['float'],
            'temp_bool': self.temp_count['bool'],
        }


# --- Tabla de variables ---
class VariableTable:
    def __init__(self):
        self.vars = {}

    def add(self, name, var_type, dir_=None):
        if name in self.vars:
            return False
        self.vars[name] = {'type': var_type, 'dir': dir_}  # 'dir' = direccion virtual (E3)
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
            'func_addr': None,   # direccion identificadora / ranura de retorno (E3)
            'mem': None,         # snapshot de memoria del frame (E3)
        }
        return True

    def get(self, name):
        return self.funcs.get(name)

    def exists(self, name):
        return name in self.funcs


# --- Manager Semantico (estado central) ---
class SemanticManager:
    def __init__(self):
        self.program_name = None  # Para validar colision con el nombre del programa
        self.func_dir = FunctionDirectory()
        self.cube = SemanticCube()
        self.mem = MemoryManager()       # memoria virtual (E3)
        self.quads = []
        self.operand_stack = []          # ahora carga DIRECCIONES (E3)
        self.operator_stack = []
        self.type_stack = []
        self.jump_stack = []
        self.break_stack = []
        self.temp_counter = 0
        self.temp_seq = 0                # secuencia para nombres legibles de temporales (E3)
        self.current_scope = 'global'
        self.current_func = None
        self.has_errors = False
        self.call_stack = []
        self.arg_counter = []
        self.names = {}                  # direccion -> nombre legible, para el debug (E3)
        self.main_jump_idx = None
        self.main_frame = None           # memoria del frame del main (E3)

    def error(self, msg):
        self.has_errors = True
        print(f"  [Error Semantico] {msg}")

    def _disp(self, v):
        # Nombre legible de una direccion/valor (para el archivo debug) (E3)
        return self.names.get(v, v)

    def new_temp(self, res_type):
        # Asigna una direccion temporal segun el tipo y guarda su nombre legible (E3)
        addr = self.mem.new_temp(res_type)
        self.temp_seq += 1
        self.names[addr] = f"t{self.temp_seq}"
        return addr

    def emit(self, op, arg1, arg2, res, type_res='-'):
        q = Quadruple(op, arg1, arg2, res, type_res)
        # captura los nombres legibles al emitir (para salida_debug.txt) (E3)
        q.arg1_name = self._disp(arg1)
        q.arg2_name = self._disp(arg2)
        q.res_name = self._disp(res)
        self.quads.append(q)
        return len(self.quads)

    def fill(self, idx, value):
        self.quads[idx - 1].res = value
        self.quads[idx - 1].res_name = value  # (E3)

    def declare_var(self, name, var_type):
        # 1. Validar que no se llame igual que el programa
        if name == self.program_name:
            self.error(f"La variable '{name}' no puede llamarse igual que el programa")
            return

        scope = self.current_scope
        func_info = self.func_dir.get(scope)
        if func_info is None:
            self.error(f"Scope '{scope}' no existe al declarar '{name}'")
            return
        # Direccion virtual segun el scope: global -> region global, funcion -> region local (E3)
        addr = self.mem.new_global(var_type) if scope == 'global' else self.mem.new_local(var_type)
        if not func_info['var_table'].add(name, var_type, addr):
            self.error(f"Variable '{name}' ya declarada en scope '{scope}'")
        else:
            func_info['num_vars'] += 1
            self.names[addr] = name  # (E3)

    def lookup_var(self, name):
        # Busca unicamente en el scope local actual (si es main, el scope es 'global')
        local = self.func_dir.get(self.current_scope)
        if local and local['var_table'].exists(name):
            return local['var_table'].get(name), self.current_scope

        # CORRECCION: Se elimino la busqueda en global si estamos dentro de una funcion.
        # Esto asegura que las variables globales NO puedan usarse en funciones locales,
        # generando el error que solicito el profesor.
        return None, None


sm = SemanticManager()

# --- 1. PALABRAS RESERVADAS Y TOKENS ---
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
t_ignore = ' \t\r'


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

# --- 2. MANEJO DE ERRORES AVANZADO CORREGIDO ---
texto_actual = ""
hubo_errores = False


def buscar_columna(input_text, token):
    line_start = input_text.rfind('\n', 0, token.lexpos) + 1
    return (token.lexpos - line_start) + 1


def p_error(p):
    global texto_actual, hubo_errores
    hubo_errores = True

    if p:
        columna = buscar_columna(texto_actual, p)
        print(f"  [Error Sintactico] Token inesperado: '{p.value}' en Linea: {p.lineno}, Columna: {columna}")
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


# --- 3. GRAMATICA LR COMPLETA ---

def p_programa(p):
    '''programa : PROGRAM ID np_prog_start SEMICOLON vars_opcional funcs_opcional MAIN np_main_start body END'''
    sm.emit('end', None, None, None, '-')
    sm.main_frame = sm.mem.snapshot_frame()  # memoria (temporales) del frame del main (E3)


def p_np_prog_start(p):
    '''np_prog_start :'''
    sm.program_name = p[-1]  # Guardar ID del programa para evitar colisiones
    sm.func_dir.add('global', T_VOID)
    sm.current_scope = 'global'
    sm.emit('gotomain', None, None, None, '-')  # salto al main (E3)
    sm.main_jump_idx = len(sm.quads)


def p_np_main_start(p):
    '''np_main_start :'''
    sm.current_scope = 'global'
    sm.mem.reset_frame()  # el main es el frame base; sus temporales arrancan limpias (E3)
    sm.fill(sm.main_jump_idx, len(sm.quads) + 1)


def p_vars_opcional_vacio(p):  '''vars_opcional : '''


def p_vars_opcional_data(p):   '''vars_opcional : vars'''


def p_funcs_opcional_vacio(p): '''funcs_opcional : '''


def p_funcs_opcional_data(p):  '''funcs_opcional : funcs'''


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

    # 1. Validar colision con nombre de programa
    if name == sm.program_name:
        sm.error(f"La funcion '{name}' no puede llamarse igual que el programa")

    # 2. Validar colision con variable global ya existente
    glob = sm.func_dir.get('global')
    if glob and glob['var_table'].exists(name):
        sm.error(f"La funcion '{name}' no puede llamarse igual que una variable global")

    if not sm.func_dir.add(name, return_type):
        sm.error(f"Funcion '{name}' ya declarada")

    sm.current_scope = name
    sm.mem.reset_frame()  # nuevo frame: locales y temporales arrancan limpias (E3)

    # Direccion identificadora de la funcion (y ranura de retorno si no es void) (E3)
    f = sm.func_dir.get(name)
    if return_type == T_VOID:
        func_addr = sm.mem.new_global(T_VOID)
    else:
        func_addr = sm.mem.new_global(return_type)
        if glob and not glob['var_table'].exists(name):
            glob['var_table'].add(name, return_type, func_addr)
    if f:
        f['func_addr'] = func_addr
    sm.names[func_addr] = name


def p_np_func_body(p):
    '''np_func_body :'''
    f = sm.func_dir.get(sm.current_scope)
    if f:
        f['quad_start'] = len(sm.quads) + 1


def p_np_func_end(p):
    '''np_func_end :'''
    f = sm.func_dir.get(sm.current_scope)
    if f and f['return_type'] != T_VOID and not _function_has_return(f):
        sm.error(f"Funcion '{sm.current_scope}' tipo '{f['return_type']}' no tiene 'return' con valor")
    sm.emit('endfun', None, None, None, '-')
    if f:
        f['mem'] = sm.mem.snapshot_frame()  # memoria requerida por el frame de la funcion (E3)
    sm.current_scope = 'global'


def _function_has_return(f):
    start = f.get('quad_start', 1) - 1
    for q in sm.quads[start:]:
        if q.op == 'return':
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
    # 1. Validar que el parametro no se llame igual que su propia funcion
    if name == sm.current_scope:
        sm.error(f"El parametro '{name}' no puede llamarse igual que la funcion")
        return

    if ptype == T_VOID:
        sm.error(f"El parametro '{name}' no puede ser de tipo 'void'")
        return
    func_info = sm.func_dir.get(sm.current_scope)
    if func_info is None:
        return
    addr = sm.mem.new_local(ptype)  # parametro ocupa una direccion local (E3)
    if not func_info['var_table'].add(name, ptype, addr):
        sm.error(f"Parametro '{name}' duplicado en funcion '{sm.current_scope}'")
        return
    func_info['params'].append((name, ptype))
    func_info['num_params'] += 1
    func_info['num_vars'] += 1
    sm.names[addr] = name  # (E3)


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
    sm.emit('goto', None, None, None, '-')
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
        sm.error(f"Variable '{p[1]}' no declarada o inaccesible (en asignacion)")
        return
    res_type = sm.cube.query('=', var['type'], tval)
    if res_type == T_ERROR:
        sm.error(f"No se puede asignar '{tval}' a '{p[1]}' ({var['type']})")
        return
    sm.emit('=', val, None, var['dir'], var['type'])  # destino = direccion de la variable (E3)


def p_print(p):
    '''print : PRINT OPEN_PAR contenido_print CLOSE_PAR SEMICOLON'''
    sm.emit('newline', None, None, None, '-')  # newline implicito al final de cada print (E3)


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
    sm.emit('print', val, None, None, '-')  # imprime el operando en arg1 (E3)


def p_cycle(p):
    '''cycle : DO np_cycle_start body WHILE OPEN_PAR expresion CLOSE_PAR np_cycle_end SEMICOLON'''
    pass


def p_np_cycle_start(p):
    '''np_cycle_start :'''
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
        sm.error(f"La condicion del while debe ser booleana, se recibio '{t}'")
    start = sm.jump_stack.pop()
    sm.emit('gotot', val, None, start, '-')
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
    if not sm.type_stack:
        return
    t = sm.type_stack.pop()
    val = sm.operand_stack.pop()
    if t != T_BOOL:
        sm.error(f"La condicion del if debe ser booleana, se recibio '{t}'")
    sm.emit('gotof', val, None, None, '-')
    sm.jump_stack.append(len(sm.quads))


def p_np_if_else(p):
    '''np_if_else :'''
    sm.emit('goto', None, None, None, '-')
    goto_idx = len(sm.quads)
    if sm.jump_stack:
        gotof_idx = sm.jump_stack.pop()
        sm.fill(gotof_idx, len(sm.quads) + 1)
    sm.jump_stack.append(goto_idx)


def p_np_if_end(p):
    '''np_if_end :'''
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
        sm.error(f"Funcion '{name}' no declarada (en llamada)")
        sm.call_stack.append(None)
        sm.arg_counter.append(0)
        return
    f = sm.func_dir.get(name)
    sm.emit('sub', f['func_addr'], None, None, '-')  # señaliza inicio de llamada (E3)
    sm.call_stack.append(name)
    sm.arg_counter.append(0)


def _call_end(name, as_expression):
    arg_count = sm.arg_counter.pop() if sm.arg_counter else 0
    func_in_stack = sm.call_stack.pop() if sm.call_stack else None
    if func_in_stack is None:
        if as_expression:
            sm.operand_stack.append('_err_')
            sm.type_stack.append(T_ERROR)
        return
    f = sm.func_dir.get(name)
    expected = len(f['params'])
    if arg_count != expected:
        sm.error(f"Funcion '{name}' espera {expected} argumento(s), recibio {arg_count}")
    start_quad = f.get('quad_start') if f.get('quad_start') is not None else -1
    sm.emit('gosub', f['func_addr'], None, start_quad, '-')  # llamada: salta al start_quad (E3)
    if as_expression:
        if f['return_type'] == T_VOID:
            sm.error(f"Funcion '{name}' es void y no puede usarse en expresion")
            sm.operand_stack.append('_err_')
            sm.type_stack.append(T_ERROR)
            return
        # copia el valor de retorno (ranura global de la funcion) a un temporal (E3)
        temp = sm.new_temp(f['return_type'])
        sm.emit('=', f['func_addr'], None, temp, f['return_type'])
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
                    f"Argumento {idx + 1} de '{func_name}': tipo '{tval}' "
                    f"incompatible con parametro '{pname}' ({ptype})"
                )
            # copia el argumento a la direccion del parametro en el frame de la funcion (E3)
            param_addr = f['var_table'].get(pname)['dir']
            sm.emit('param', val, None, param_addr, '-')
    if sm.arg_counter:
        sm.arg_counter[-1] += 1


def p_return_stmt_val(p):
    '''return_stmt : RETURN expresion SEMICOLON'''
    if not sm.operand_stack:
        return
    val = sm.operand_stack.pop()
    tval = sm.type_stack.pop()
    if sm.current_scope == 'global':
        sm.error("'return' fuera de una funcion")
        return
    f = sm.func_dir.get(sm.current_scope)
    if f['return_type'] == T_VOID:
        sm.error(f"Funcion '{sm.current_scope}' es void y no debe retornar un valor")
        return
    res = sm.cube.query('=', f['return_type'], tval)
    if res == T_ERROR:
        sm.error(
            f"Tipo de retorno '{tval}' incompatible con tipo '{f['return_type']}'"
        )
        return
    # guarda el valor en la ranura de retorno (direccion global de la funcion) y regresa (E3)
    sm.emit('=', val, None, f['func_addr'], f['return_type'])
    sm.emit('return', None, None, None, '-')


def p_return_stmt_empty(p):
    '''return_stmt : RETURN SEMICOLON'''
    if sm.current_scope == 'global':
        sm.error("'return' fuera de una funcion")
        return
    f = sm.func_dir.get(sm.current_scope)
    if f['return_type'] != T_VOID:
        sm.error(
            f"Funcion '{sm.current_scope}' tipo '{f['return_type']}' debe retornar un valor"
        )
        return
    sm.emit('return', None, None, None, '-')


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
    temp = sm.new_temp(res_type)  # temporal con direccion segun el tipo resultante (E3)
    sm.emit(op, left, right, temp, res_type)
    sm.operand_stack.append(temp)
    sm.type_stack.append(res_type)


def p_factor_nested(p):
    '''factor : OPEN_PAR expresion CLOSE_PAR'''
    pass


def p_factor_unary_sum(p):
    '''factor : OP_SUM factor'''
    pass


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
    zero = sm.mem.new_const(0, T_INT)  # el 0 tambien es una constante con direccion (E3)
    sm.names[zero] = 0
    temp = sm.new_temp(res_type)
    sm.emit('-', zero, val, temp, res_type)
    sm.operand_stack.append(temp)
    sm.type_stack.append(res_type)


def p_factor_base(p):
    '''factor : base'''
    pass


def p_factor_id(p):
    '''factor : ID'''
    var, _ = sm.lookup_var(p[1])
    if var is None:
        sm.error(f"Variable '{p[1]}' no declarada o inaccesible (en expresion)")
        sm.operand_stack.append(p[1])
        sm.type_stack.append(T_ERROR)
    else:
        sm.operand_stack.append(var['dir'])  # empuja la direccion de la variable (E3)
        sm.type_stack.append(var['type'])


def p_factor_f_call(p):
    '''factor : ID np_call_start OPEN_PAR argumentos_opc CLOSE_PAR'''
    _call_end(p[1], as_expression=True)


def p_base_cte_int(p):
    '''base : CTE_INT'''
    addr = sm.mem.new_const(p[1], T_INT)  # (E3)
    sm.names[addr] = p[1]
    sm.operand_stack.append(addr)
    sm.type_stack.append(T_INT)


def p_base_cte_float(p):
    '''base : CTE_FLOAT'''
    addr = sm.mem.new_const(p[1], T_FLOAT)  # (E3)
    sm.names[addr] = p[1]
    sm.operand_stack.append(addr)
    sm.type_stack.append(T_FLOAT)


def p_base_cte_str(p):
    '''base : CTE_STR'''
    addr = sm.mem.new_const(p[1], T_STRING)  # (E3)
    sm.names[addr] = p[1]
    sm.operand_stack.append(addr)
    sm.type_stack.append(T_STRING)


parser = yacc.yacc(debug=False, write_tables=False)  # sin generar parser.out / parsetab.py (E3)


# --- 4. EMISION DE LA REPRESENTACION INTERMEDIA ---

def _format_cell(v):
    return '_' if v is None else str(v)


def format_quads(quads):
    # Cuadruplos con NOMBRES legibles (para salida_debug.txt) (E3)
    lines = []
    header = f"{'#':>4} | {'OP':<9} | {'ARG1':<16} | {'ARG2':<16} | {'RES':<16} | TIPO"
    lines.append(header)
    lines.append("-" * len(header))
    for i, q in enumerate(quads, start=1):
        lines.append(
            f"{i:>4} | {q.op:<9} | "
            f"{_format_cell(q.arg1_name):<16} | "
            f"{_format_cell(q.arg2_name):<16} | "
            f"{_format_cell(q.res_name):<16} | "
            f"{q.type_res}"
        )
    return "\n".join(lines)


# Orden fijo de los contadores de memoria global (convencion de clase) (E3)
GLOBAL_MEM_ORDER = [
    'global_int', 'global_float', 'global_str', 'global_void',
    'temp_int', 'temp_float', 'temp_bool',
    'cte_int', 'cte_float', 'cte_str',
]


def build_obj(manager):
    """Representacion intermedia en DIRECCIONES (lo ejecuta la VM). (E3)
    Secciones: constantes, contadores de memoria, bloques por funcion y cuadruplos."""
    m = manager.mem
    main_frame = manager.main_frame or {'temp_int': 0, 'temp_float': 0, 'temp_bool': 0}
    out = []

    # 1) Constantes: valor  direccion
    out.append("%%CONSTANTS")
    for (value, _t), addr in sorted(m.const_table.items(), key=lambda kv: kv[1]):
        out.append(f"{value}\t{addr}")

    # 2) Contadores de memoria global (incluye temporales del main)
    out.append("%%GLOBALMEM")
    counts = {
        'global_int': m.global_count['int'], 'global_float': m.global_count['float'],
        'global_str': m.global_count['string'], 'global_void': m.global_count['void'],
        'temp_int': main_frame['temp_int'], 'temp_float': main_frame['temp_float'],
        'temp_bool': main_frame['temp_bool'],
        'cte_int': m.const_count['int'], 'cte_float': m.const_count['float'],
        'cte_str': m.const_count['string'],
    }
    for k in GLOBAL_MEM_ORDER:
        out.append(f"{k}\t{counts[k]}")

    # 3) Bloque de memoria por funcion (dimensiona cada frame en la VM)
    out.append("%%FUNCTIONS")
    for name, f in manager.func_dir.funcs.items():
        if name == 'global':
            continue
        fm = f['mem'] or {}
        ret = f['func_addr'] if f['return_type'] != T_VOID else -1
        out.append(
            f"{f['func_addr']}\t{f['quad_start']}\t{f['num_params']}\t"
            f"{fm.get('local_int', 0)}\t{fm.get('local_float', 0)}\t{fm.get('local_str', 0)}\t"
            f"{fm.get('temp_int', 0)}\t{fm.get('temp_float', 0)}\t{fm.get('temp_bool', 0)}\t{ret}"
        )

    # 4) Cuadruplos en direcciones
    out.append("%%QUADS")
    for i, q in enumerate(manager.quads, start=1):
        out.append(f"{i}\t{q.op}\t{_cell(q.arg1)}\t{_cell(q.arg2)}\t{_cell(q.res)}")

    out.append("%%END")
    return "\n".join(out) + "\n"


def _cell(v):
    return -1 if v is None else v


def format_symbol_table(func_dir):
    lines = []
    lines.append("TABLA DE SIMBOLOS")
    lines.append("-" * 17)

    glob = func_dir.get('global')
    if glob:
        lines.append("\n[Scope: global]")
        if not glob['var_table'].vars:
            lines.append("  (sin variables)")
        for name, info in glob['var_table'].vars.items():
            lines.append(f"  - {name}: {info['type']}  @ dir {info['dir']}")

    lines.append("\n[Directorio de funciones]")
    user_funcs = {n: f for n, f in func_dir.funcs.items() if n != 'global'}
    if not user_funcs:
        lines.append("  (sin funciones de usuario)")
    for fname, finfo in user_funcs.items():
        params_str = ", ".join(f"{n}:{t}" for n, t in finfo['params']) or "(sin parametros)"
        lines.append(
            f"  - {fname}({params_str}) -> {finfo['return_type']}  "
            f"[inicio quad: {finfo.get('quad_start', '-')}, "
            f"params: {finfo['num_params']}, vars: {finfo['num_vars']}]"
        )
        lines.append(f"      Variables locales:")
        if not finfo['var_table'].vars:
            lines.append("        (ninguna)")
        for name, info in finfo['var_table'].vars.items():
            lines.append(f"        - {name}: {info['type']}  @ dir {info['dir']}")
    return "\n".join(lines)


# --- 5. MAIN PRINCIPAL (ENTREGA 3) ---
# Abre un unico source code (input.txt por defecto, o el dado por terminal),
# lo compila (lexico, sintaxis, semantica, representacion intermedia) y, si es
# valido, ejecuta su representacion intermedia en la maquina virtual.
if __name__ == '__main__':
    from vm import VirtualMachine  # la VM es un programa independiente

    nombre_archivo = sys.argv[1] if len(sys.argv) > 1 else "input.txt"
    texto_actual = open(nombre_archivo, encoding="utf-8").read()

    parser.parse(texto_actual, lexer=lexer)

    if hubo_errores or sm.has_errors:
        # Los errores de compilacion ya se imprimieron con su linea. Abortar.
        sys.exit(1)

    # Representacion intermedia: en DIRECCIONES (obj.txt, ejecutado por la VM)
    # y en NOMBRES (salida_debug.txt, para depuracion).
    obj_text = build_obj(sm)
    with open("obj.txt", "w", encoding="utf-8") as fout:
        fout.write(obj_text)
    with open("salida_debug.txt", "w", encoding="utf-8") as fout:
        fout.write(format_quads(sm.quads) + "\n\n" + format_symbol_table(sm.func_dir) + "\n")

    # Ejecuta la representacion intermedia en la maquina virtual.
    vm = VirtualMachine()
    vm.load(obj_text)
    vm.run()