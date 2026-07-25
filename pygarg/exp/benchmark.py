import sys
from pathlib import Path

# 1. Obtenemos la ruta absoluta de la carpeta donde está este script (exp/)
ruta_actual = Path(__file__).resolve().parent

# 2. Subimos un nivel y entramos en 'src'
ruta_src = ruta_actual.parent / "src"

# 3. Añadimos esa ruta al sistema de búsqueda de Python
sys.path.append(str(ruta_src))


import time
import networkx as nx
from pathlib import Path
import pygarg.dung.apx_parser
import random

import pygarg.dung.solver

def reduccion_simplicial(args, atts):
    """
    Transforma un AF en un W-QBAF utilizando pygarg (SAT solver) 
    para extraer los conjuntos CF y filtrarlos a maximales.
    """
    # 1. Delegar a pygarg la búsqueda de TODOS los conjuntos libres de conflicto (CF)
    extensiones_cf = list(pygarg.dung.solver.extension_enumeration(args, atts, 'PR'))
    
    # 2. Convertir a sets y ordenar por tamaño (de mayor a menor) para optimizar el filtrado
    cf_sets = sorted([set(ext) for ext in extensiones_cf], key=len, reverse=True)
    
    facetas = []
    # Filtrar para quedarse solo con los conjuntos maximales (las facetas reales)
    for cf in cf_sets:
        # Si este conjunto 'cf' no es subconjunto de ninguna faceta ya encontrada, es maximal
        if not any(cf.issubset(f) for f in facetas):
            facetas.append(cf)
            
    # Mapear cada faceta a un ID de meta-argumento (X_1, X_2, ...)
    A_star = {f"X_{i+1}": faceta for i, faceta in enumerate(facetas)}
    
    # 3. Construir diccionarios de adyacencia
    out_adj = {arg: set() for arg in args}
    in_adj = {arg: set() for arg in args}
    
    for atacante, atacado in atts:
        out_adj[atacante].add(atacado)
        in_adj[atacado].add(atacante)

    R_star = []
    pesos_w = {}
    valoraciones_tau = {}
    
    # 4. Calcular la función de peso w(X, Y) y la relación de ataque R*
    for id_X, X in A_star.items():
        for id_Y, Y in A_star.items():
            if id_X == id_Y: 
                continue
            
            atacantes = {x for x in X if not out_adj[x].isdisjoint(Y)}
            
            if atacantes:
                R_star.append((id_X, id_Y))
                pesos_w[(id_X, id_Y)] = len(atacantes) / len(X)
                
    # 5. Calcular la Valoración Base (Tau) conservando el rol dialéctico externo
    for id_X, X in A_star.items():
        r_out = 0
        r_in = 0
        
        for x in X:
            r_out += len([tgt for tgt in out_adj[x] if tgt not in X])
            r_in += len([src for src in in_adj[x] if src not in X])
            
        if (r_out + r_in) == 0:
            valoraciones_tau[id_X] = 0.5
        else:
            valoraciones_tau[id_X] = 0.5 * (((r_out - r_in) / (r_out + r_in)) + 1.0)
            
    return A_star, R_star, pesos_w, valoraciones_tau

def ejecutar_benchmark(ruta_archivo):
    """
    Compara las métricas del grafo original frente al grafo reducido W-QBAF.
    """
    print(f"\nProcesando instancia: {ruta_archivo.name}")
    args, atts = pygarg.dung.apx_parser.parse(str(ruta_archivo))
    
    inicio = time.time()
    A_star, R_star, pesos_w, valoraciones_tau = reduccion_simplicial(args, atts)
    tiempo_total = time.time() - inicio
    
    nodos_orig = len(args)
    aristas_orig = len(atts)
    nodos_red = len(A_star)
    aristas_red = len(R_star)
    
    # Imprimir métricas de compresión
    print("-" * 40)
    print(f"Grafo Original (AF)       -> Nodos: {nodos_orig:4d} | Ataques: {aristas_orig:4d}")
    print(f"Grafo Reducido (W-QBAF)   -> Nodos: {nodos_red:4d} | Ataques: {aristas_red:4d}")
    print("-" * 40)
    print(f"Compresión de Nodos       : {(nodos_red / nodos_orig) * 100:.1f}% del original")
    print(f"Tiempo de reducción       : {tiempo_total:.4f} s")
    
    return A_star, R_star, pesos_w, valoraciones_tau

# --- Ejemplo de uso ---
def ejecutar_muestras_aleatorias(ruta_carpeta, num_muestras):
    """
    Busca todos los archivos .apx en la carpeta, elige 'num_muestras' al azar 
    y ejecuta el benchmark de reducción simplicial en cada uno.
    """
    carpeta = Path(ruta_carpeta)
    
    # 1. Recopilar todos los archivos .apx disponibles en esa carpeta
    archivos_apx = list(carpeta.glob("*.apx"))
    
    if not archivos_apx:
        print(f"Error: No se han encontrado archivos .apx en {carpeta}")
        return
        
    # 2. Ajustar la cantidad por si pides más archivos de los que realmente hay
    cantidad_real = min(num_muestras, len(archivos_apx))
    
    # 3. Seleccionar los archivos al azar
    seleccion = random.sample(archivos_apx, cantidad_real)
    
    print(f"\n=== Iniciando simulación con {cantidad_real} grafos aleatorios desde {carpeta.name} ===")
    
    # 4. Bucle para probar cada uno
    for archivo in seleccion:
        try:
            ejecutar_benchmark(archivo)
        except Exception as e:
            print(f"Error procesando {archivo.name}: {e}")

if __name__ == "__main__":
    # Apuntamos a la carpeta ER usando tu estructura de directorios
    # ruta_actual ya está definida arriba en tu script (es la carpeta exp/)
    carpeta_er = ruta_actual / "instances" / "BA"
    
    # Lanza la función pidiendo, por ejemplo, 5 grafos al azar
    ejecutar_muestras_aleatorias(carpeta_er, num_muestras=50)