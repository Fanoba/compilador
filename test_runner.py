import subprocess
import sys

# Definir las pruebas: (Archivo, [Textos esperados en la consola], Debe_Fallar?)
pruebas = [
    ("casos_prueba/test_exito.txt", ["Programa estructurado correctamente"], False),
    ("casos_prueba/test_scopes.txt", ["no declarada o inaccesible"], True),
    ("casos_prueba/test_colision.txt", [
        "no puede llamarse igual que el programa",
        "no puede llamarse igual que una variable global",
        "no puede llamarse igual que la funcion"
    ], True)
]

def correr_pruebas():
    exito_total = True
    print("=== INICIANDO PRUEBAS AUTOMATICAS ===")

    for archivo, textos_esperados, debe_fallar in pruebas:
        print(f"\nProbando: {archivo} ...")
        # Ejecutamos tu compilador mandándole el archivo
        resultado = subprocess.run(['python', 'main.py', archivo], capture_output=True, text=True)
        salida = resultado.stdout + resultado.stderr

        paso_prueba = True

        # Revisamos si imprimió exactamente lo que esperábamos
        for texto in textos_esperados:
            if texto not in salida:
                print(f"  [X] ERROR: Faltó el mensaje esperado -> '{texto}'")
                paso_prueba = False

        # Revisamos si detectó error o no
        hubo_errores = "[!] Hubo errores" in salida
        if debe_fallar and not hubo_errores:
            print("  [X] ERROR: El programa debió fallar pero pasó la compilación.")
            paso_prueba = False
        elif not debe_fallar and hubo_errores:
            print("  [X] ERROR: El programa debió compilar bien pero falló.")
            paso_prueba = False

        if paso_prueba:
            print("  [OK] Prueba superada.")
        else:
            exito_total = False
            # ¡NUEVO!: Imprimir exactamente qué vio el compilador para poder depurar
            print("\n--- 🔍 DETALLE DEL ERROR (SALIDA DEL COMPILADOR) ---")
            print(salida)
            print("--------------------------------------------------\n")

    print("\n=== RESULTADO FINAL ===")
    if exito_total:
        print("Todas las pruebas pasaron. El código es seguro.")
        sys.exit(0)
    else:
        print("Algunas pruebas fallaron. Revisa los cambios.")
        sys.exit(1)

if __name__ == '__main__':
    correr_pruebas()