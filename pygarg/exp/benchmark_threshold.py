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

import statistics

def reduccion_simplicial(args, atts, umbral=0.5):
    """
    Transforma un AF en un W-QBAF comprimiendo los argumentos.
    Permite usar un umbral de poda fijo o, si es None, calcula un umbral 
    dinámico basado en la media de los pesos teóricos.
    """
    # 1. Pedir todas las extensiones CF a pygarg
    extensiones_brutas = list(pygarg.dung.solver.extension_enumeration(args, atts, 'CF'))

    # 2. Quitar el conjunto vacío y convertir las listas a sets
    facetas_todas = [set(ext) for ext in extensiones_brutas if ext]

    # 3. Aplicar el filtro estricto de maximalidad (Punto 2 del revisor)
    # Solo nos quedamos con 'f' si NO es un subconjunto estricto (<) de ningún otro conjunto 'g'
    facetas = [f for f in facetas_todas if not any(f < g for g in facetas_todas if f != g)]

    # 4. Mapear cada faceta real a su ID de meta-argumento
    A_star_inicial = {f"X_{i+1}": faceta for i, faceta in enumerate(facetas)}
    
    out_adj = {arg: set() for arg in args}
    in_adj = {arg: set() for arg in args}
    for atacante, atacado in atts:
        out_adj[atacante].add(atacado)
        in_adj[atacado].add(atacante)

    pesos_brutos = {}
    
    # 2. Calcular todos los pesos teóricos w(X,Y) sin filtrar
    for id_X, X in A_star_inicial.items():
        for id_Y, Y in A_star_inicial.items():
            if id_X == id_Y: 
                continue
            
            atacantes = {x for x in X if not out_adj[x].isdisjoint(Y)}
            if atacantes:
                # Ecuación de peso w(X,Y)
                pesos_brutos[(id_X, id_Y)] = len(atacantes) / len(X)
                
    # 3. Determinar el umbral a aplicar
    if not pesos_brutos:
        # Grafo sin ataques entre coaliciones
        umbral_aplicado = 0.0
    elif umbral is not None:
        umbral_aplicado = umbral
    else:
        # Umbral dinámico: media aritmética de los pesos calculados
        umbral_aplicado = statistics.mean(pesos_brutos.values())
    
    # 4. Filtrar usando el umbral seleccionado
    R_star_filtrado = []
    pesos_w_finales = {}
    nodos_conectados = set()
    
    for (origen, destino), peso in pesos_brutos.items():
        if peso >= umbral_aplicado:
            R_star_filtrado.append((origen, destino))
            pesos_w_finales[(origen, destino)] = peso
            nodos_conectados.add(origen)
            nodos_conectados.add(destino)
            
    # Separamos los nodos aislados (invictos) de la topología principal conectada
    A_star_conectados = {id_X: X for id_X, X in A_star_inicial.items() if id_X in nodos_conectados}
    A_star_aislados = {id_X: X for id_X, X in A_star_inicial.items() if id_X not in nodos_conectados}
    
    # 5. Calcular la Valoración Base (Tau) conservando el rol dialéctico externo
    valoraciones_tau = {}
    for id_X, X in A_star_conectados.items():
        r_out = sum(len([tgt for tgt in out_adj[x] if tgt not in X]) for x in X)
        r_in = sum(len([src for src in in_adj[x] if src not in X]) for x in X)
        
        if (r_out + r_in) == 0:
            valoraciones_tau[id_X] = 0.5
        else:
            valoraciones_tau[id_X] = 0.5 * (((r_out - r_in) / (r_out + r_in)) + 1.0)
            
    # Asignar tau = 0.5 a los aislados por definición
    for id_X in A_star_aislados.keys():
        valoraciones_tau[id_X] = 0.5
            
    return A_star_conectados, A_star_aislados, R_star_filtrado, pesos_w_finales, valoraciones_tau, umbral_aplicado

def ejecutar_benchmark(ruta_archivo, umbral_manual=None):
    """
    Compara las métricas del grafo original frente al grafo reducido W-QBAF,
    soportando nodos aislados y umbrales dinámicos.
    """
    print(f"\nProcesando instancia: {ruta_archivo.name}")
    args, atts = pygarg.dung.apx_parser.parse(str(ruta_archivo))
    
    inicio = time.time()
    
    # Desempaquetamos los 6 valores que devuelve la función híbrida
    conectados, aislados, R_star, pesos_w, valoraciones_tau, umbral_usado = reduccion_simplicial(args, atts, umbral=umbral_manual)
    
    tiempo_total = time.time() - inicio
    
    nodos_orig = len(args)
    aristas_orig = len(atts)
    
    # Calculamos los nodos reducidos totales
    nodos_red_conectados = len(conectados)
    nodos_red_aislados = len(aislados)
    nodos_red_total = nodos_red_conectados + nodos_red_aislados
    
    aristas_red = len(R_star)
    
    # Imprimir métricas de compresión
    print("-" * 50)
    print(f"Grafo Original (AF)       -> Nodos: {nodos_orig:4d} | Ataques: {aristas_orig:4d}")
    print(f"Grafo Reducido (W-QBAF)   -> Nodos: {nodos_red_total:4d} | Ataques: {aristas_red:4d}")
    print(f"  - Conectados: {nodos_red_conectados} | Aislados (Tau=0.5): {nodos_red_aislados}")
    print("-" * 50)
    print(f"Umbral aplicado           : {umbral_usado:.3f}")
    print(f"Compresión de Nodos       : {(nodos_red_total / nodos_orig) * 100:.1f}% del original")
    print(f"Tiempo de reducción       : {tiempo_total:.4f} s")
    
    return conectados, aislados, R_star, pesos_w, valoraciones_tau

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
    carpeta_er = ruta_actual / "instances" / "ER"
    
    # Lanza la función pidiendo, por ejemplo, 5 grafos al azar
    ejecutar_muestras_aleatorias(carpeta_er, num_muestras=50)