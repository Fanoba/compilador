"""
Little Duck - Quack Virtual Machine (Entrega 3)
Maquina virtual INDEPENDIENTE: carga un obj.txt en direcciones de memoria
virtual y lo interpreta.

Uso standalone:  python vm.py obj.txt

Memoria simulada por regiones (convencion de clase):
  global / constantes -> memoria global unica y compartida
  local / temporal    -> viven en el activation record (frame) de cada llamada
"""

import sys

RECURSION_LIMIT = 1000

# Rangos de direcciones por region (inicio, fin inclusivo)
GLOBAL_RANGE = (1000, 6999)     # global int/float/str/void
LOCAL_RANGE = (7000, 11999)     # local int/float/str
TEMP_RANGE = (12000, 16999)     # temp int/float/bool
CONST_RANGE = (17000, 19999)    # const int/float/str


class RuntimeErrorVM(Exception):
    """Error de semantica en tiempo de ejecucion (aborta el programa)."""
    pass


class Frame:
    """Activation record: memoria local+temporal propia y direccion de retorno."""
    def __init__(self, return_ip):
        self.mem = {}
        self.return_ip = return_ip


class VirtualMachine:
    def __init__(self):
        self.global_mem = {}        # globales + constantes (compartido)
        self.quads = []             # lista de (op, arg1, arg2, res)
        self.func_table = {}        # func_addr -> info de memoria del frame
        self.call_stack = []
        self.pending_frame = None   # frame en construccion (entre sub y gosub)
        self.ip = 1                 # apuntador de instruccion (1-based)

    # ---------- Carga del obj.txt ----------
    def load(self, text):
        section = None
        for raw in text.splitlines():
            line = raw.rstrip('\n')
            if not line.strip():
                continue
            if line.startswith('%%'):
                section = line.strip()
                continue
            parts = line.split('\t')
            if section == '%%CONSTANTS':
                value, addr = parts[0], int(parts[1])
                self.global_mem[addr] = self._parse_const(value, addr)
            elif section == '%%GLOBALMEM':
                pass  # contadores informativos
            elif section == '%%FUNCTIONS':
                # func_addr start_quad params li lf ls ti tf tb ret
                vals = [int(x) for x in parts]
                self.func_table[vals[0]] = {
                    'start_quad': vals[1], 'params': vals[2],
                    'return': vals[9],
                }
            elif section == '%%QUADS':
                # num op arg1 arg2 res
                num = int(parts[0])
                op = parts[1]
                arg1 = int(parts[2])
                arg2 = int(parts[3])
                res = int(parts[4])
                self.quads.append((op, arg1, arg2, res))

    def load_file(self, path):
        with open(path, encoding='utf-8') as f:
            self.load(f.read())

    @staticmethod
    def _parse_const(value, addr):
        if CONST_RANGE[0] <= addr < 18000:          # cte_int
            return int(value)
        if 18000 <= addr < 19000:                   # cte_float
            return float(value)
        # cte_str: quita comillas y resuelve escapes basicos
        s = value
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            s = s[1:-1]
        return s.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')

    # ---------- Acceso a memoria (ruteo por region) ----------
    def _region(self, addr):
        if GLOBAL_RANGE[0] <= addr <= GLOBAL_RANGE[1]:
            return 'global'
        if CONST_RANGE[0] <= addr <= CONST_RANGE[1]:
            return 'global'
        if LOCAL_RANGE[0] <= addr <= LOCAL_RANGE[1]:
            return 'frame'
        if TEMP_RANGE[0] <= addr <= TEMP_RANGE[1]:
            return 'frame'
        raise RuntimeErrorVM(f"Direccion fuera de las regiones de memoria virtual: {addr}")

    def get_value(self, addr):
        region = self._region(addr)
        store = self.global_mem if region == 'global' else self.call_stack[-1].mem
        if addr not in store:
            raise RuntimeErrorVM(f"Acceso a memoria virtual sin reservar/inicializar (direccion {addr})")
        return store[addr]

    def set_value(self, addr, value, target_frame=None):
        region = self._region(addr)
        if region == 'global':
            self.global_mem[addr] = value
        else:
            frame = target_frame if target_frame is not None else self.call_stack[-1]
            frame.mem[addr] = value

    # ---------- Ejecucion ----------
    def run(self):
        # Frame base = el main
        self.call_stack.append(Frame(return_ip=None))
        self.ip = 1
        n = len(self.quads)
        while 1 <= self.ip <= n:
            op, a1, a2, res = self.quads[self.ip - 1]
            try:
                advanced = self._exec(op, a1, a2, res)
            except RuntimeErrorVM as e:
                print(f"\n[Error en runtime] {e}  (cuadruplo {self.ip})")
                return False
            except ZeroDivisionError:
                print(f"\n[Error en runtime] Division entre cero  (cuadruplo {self.ip})")
                return False
            if not advanced:
                self.ip += 1
        return True

    def _exec(self, op, a1, a2, res):
        """Ejecuta un cuadruplo. Devuelve True si ya modifico el ip (salto)."""
        if op == 'gotomain':
            self.ip = res
            return True

        if op == '=':
            self.set_value(res, self.get_value(a1))
            return False

        if op in ('+', '-', '*', '/'):
            self._arith(op, a1, a2, res)
            return False

        if op in ('>', '<', '>=', '<=', '==', '!='):
            self._relational(op, a1, a2, res)
            return False

        if op == 'gotof':
            if not self.get_value(a1):
                self.ip = res
                return True
            return False

        if op == 'gotot':
            if self.get_value(a1):
                self.ip = res
                return True
            return False

        if op == 'goto':
            self.ip = res
            return True

        if op == 'print':
            print(self._format(self.get_value(a1)), end='')
            return False

        if op == 'newline':
            print()
            return False

        if op == 'sub':
            # prepara un frame nuevo para la funcion en a1
            self.pending_frame = Frame(return_ip=None)
            self.pending_frame.func_addr = a1
            return False

        if op == 'param':
            # copia el argumento (frame actual) al parametro destino del frame nuevo
            self.pending_frame.mem[res] = self.get_value(a1)
            return False

        if op == 'gosub':
            if len(self.call_stack) >= RECURSION_LIMIT:
                raise RuntimeErrorVM(f"Recursion maxima excedida (limite {RECURSION_LIMIT})")
            # la direccion de retorno es el cuadruplo siguiente al gosub
            self.pending_frame.return_ip = self.ip + 1
            self.call_stack.append(self.pending_frame)
            self.pending_frame = None
            self.ip = res
            return True

        if op in ('endfun', 'return'):
            frame = self.call_stack.pop()
            self.ip = frame.return_ip
            return True

        if op == 'end':
            self.ip = 0  # detiene el ciclo
            return True

        raise RuntimeErrorVM(f"Operador desconocido: {op}")

    def _arith(self, op, a1, a2, res):
        x = self.get_value(a1)
        y = self.get_value(a2)
        if op == '+':
            r = x + y
        elif op == '-':
            r = x - y
        elif op == '*':
            r = x * y
        else:  # division
            if y == 0:
                raise RuntimeErrorVM("Division entre cero")
            if isinstance(x, int) and isinstance(y, int):
                r = int(x / y)   # int/int -> int (trunca hacia cero)
            else:
                r = x / y
        self.set_value(res, r)

    def _relational(self, op, a1, a2, res):
        x = self.get_value(a1)
        y = self.get_value(a2)
        r = {
            '>': x > y, '<': x < y, '>=': x >= y, '<=': x <= y,
            '==': x == y, '!=': x != y,
        }[op]
        self.set_value(res, r)

    @staticmethod
    def _format(v):
        if isinstance(v, bool):
            return 'true' if v else 'false'
        return str(v)


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else "obj.txt"
    vm = VirtualMachine()
    vm.load_file(path)
    vm.run()
