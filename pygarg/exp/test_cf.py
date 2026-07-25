import sys
from pathlib import Path

# Configuración de rutas (como ya tenías en tus scripts)
ruta_actual = Path(__file__).resolve().parent
ruta_src = ruta_actual.parent / "src"
sys.path.append(str(ruta_src))

import pygarg.dung.solver

def test_punto_1():
    # 1. Los 4 nodos de la Fig. 4
    args = ['a', 'b', 'c', 'd']
    
    # 2. Los ataques que generan las facetas del paper {a,b}, {a,d}, {b,c}
    atts = [('c', 'a'), ('d', 'c'), ('b', 'd')]
    
    # 3. Pedimos a pygarg la semántica CF
    print("Calculando semántica 'CF' con pygarg...\n")
    extensiones_cf = list(pygarg.dung.solver.extension_enumeration(args, atts, 'CF'))
    
    # Convertimos a sets y ordenamos por tamaño para leerlo mejor
    facetas = sorted([set(ext) for ext in extensiones_cf], key=len)
    
    print(f"Total de conjuntos devueltos: {len(facetas)}\n")
    for f in facetas:
        print(f)

if __name__ == "__main__":
    test_punto_1()