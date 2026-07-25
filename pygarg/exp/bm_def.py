import sys
import time
import random
import statistics
import re
from pathlib import Path

# 1. Configuración dinámica de rutas
ruta_actual = Path(__file__).resolve().parent
ruta_src = ruta_actual.parent / "src"
sys.path.append(str(ruta_src))

import pygarg.dung.apx_parser
import pygarg.dung.solver

def reduccion_simplicial_maximal(args, atts, umbral_manual=None):
    """
    Transforma un AF en un W-QBAF utilizando pygarg para extraer 
    EXCLUSIVAMENTE los conjuntos libres de conflicto maximales (facetas).
    Incluye lógica de poda adaptativa (umbral) para limpiar ataques débiles.
    """
    # 1. Extraer semántica CF y aplicar el filtro de maximalidad
    extensiones_cf = list(pygarg.dung.solver.extension_enumeration(args, atts, 'CO'))
    
    # Descartar conjunto vacío y convertir a sets
    facetas_todas = [set(ext) for ext in extensiones_cf if ext]
    
    # Conservar solo los maximales (no son subconjunto estricto de ningún otro)
    facetas = [f for f in facetas_todas if not any(f < g for g in facetas_todas if f != g)]
    
    # Mapear cada faceta a su ID de meta-argumento
    A_star_inicial = {f"X_{i+1}": set(faceta) for i, faceta in enumerate(facetas)}
    
    # 2. Construir diccionarios de adyacencia ultrarrápidos
    out_adj = {arg: set() for arg in args}
    in_adj = {arg: set() for arg in args}
    for atacante, atacado in atts:
        out_adj[atacante].add(atacado)
        in_adj[atacado].add(atacante)

    pesos_brutos = {}
    
    # 3. Calcular todos los pesos teóricos w(X, Y) sin filtrar
    for id_X, X in A_star_inicial.items():
        for id_Y, Y in A_star_inicial.items():
            if id_X == id_Y: 
                continue
            
            # Intersección entre los ataques lanzados por X y los nodos de Y
            atacantes = {x for x in X if not out_adj[x].isdisjoint(Y)}
            
            if atacantes:
                pesos_brutos[(id_X, id_Y)] = len(atacantes) / len(X)
                
    # 4. Determinar el umbral a aplicar
    if not pesos_brutos:
        umbral_aplicado = 0.0
    elif umbral_manual is not None:
        umbral_aplicado = umbral_manual
    else:
        # Umbral dinámico: media aritmética de los pesos brutos
        umbral_aplicado = statistics.mean(pesos_brutos.values())
        
    # 5. Filtrar usando el umbral seleccionado
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
    
    # 6. Calcular la Valoración Base (Tau) para la semántica gradual de los conectados
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

def ejecutar_benchmark(ruta_archivo, umbral_manual=0.1):
    """
    Lee un archivo .apx, ejecuta la reducción simplicial maximal 
    e imprime las métricas de compresión y rendimiento.
    """
    print(f"\nProcesando instancia: {ruta_archivo.name}")
    args, atts = pygarg.dung.apx_parser.parse(str(ruta_archivo))
    
    inicio = time.time()
    
    # Desempaquetar las 6 variables devueltas
    conectados, aislados, R_star, pesos_w, valoraciones_tau, umbral_usado = reduccion_simplicial_maximal(args, atts, umbral_manual)
    
    tiempo_total = time.time() - inicio
    
    nodos_orig = len(args)
    aristas_orig = len(atts)
    
    nodos_red_conectados = len(conectados)
    nodos_red_aislados = len(aislados)
    nodos_red_total = nodos_red_conectados + nodos_red_aislados
    aristas_red = len(R_star)
    
    # Imprimir métricas por consola
    print("-" * 50)
    print(f"Grafo Original (AF)       -> Nodos: {nodos_orig:4d} | Ataques: {aristas_orig:4d}")
    print(f"Grafo Reducido (W-QBAF)   -> Nodos: {nodos_red_total:4d} | Ataques: {aristas_red:4d}")
    print(f"  - Conectados: {nodos_red_conectados} | Aislados (Tau=0.5): {nodos_red_aislados}")
    print("-" * 50)
    print(f"Umbral aplicado           : {umbral_usado:.3f}")
    
    if nodos_orig > 0:
        compresion = (nodos_red_total / nodos_orig) * 100
        print(f"Compresión de Nodos       : {compresion:.1f}% del original")
    else:
        print("Compresión de Nodos       : N/A (Grafo vacío)")
        
    print(f"Tiempo de reducción       : {tiempo_total:.4f} s")
    
    return conectados, aislados, R_star, pesos_w, valoraciones_tau

def ejecutar_muestras_aleatorias(ruta_carpeta, num_muestras, max_args=20, umbral_manual=0):
    """
    Selecciona archivos .apx al azar de una carpeta, filtrando 
    para procesar únicamente aquellos con un máximo de 'max_args'.
    """
    carpeta = Path(ruta_carpeta)
    archivos_apx = list(carpeta.glob("*.apx"))
    
    if not archivos_apx:
        print(f"Error: No se han encontrado archivos .apx en {carpeta}")
        return
        
    archivos_filtrados = []
    
    # Filtrar los archivos leyendo el 'numArg' del nombre
    for archivo in archivos_apx:
        match = re.search(r'numArg(\d+)', archivo.name)
        if match:
            num_nodos = int(match.group(1))
            if num_nodos <= max_args:
                archivos_filtrados.append(archivo)
                
    if not archivos_filtrados:
        print(f"Error: No hay instancias con {max_args} argumentos o menos.")
        return
        
    cantidad_real = min(num_muestras, len(archivos_filtrados))
    seleccion = random.sample(archivos_filtrados, cantidad_real)
    
    print(f"\n=== Iniciando simulación con {cantidad_real} grafos aleatorios (Max {max_args} nodos) desde {carpeta.name} ===")
    
    for archivo in seleccion:
        try:
            ejecutar_benchmark(archivo, umbral_manual)
        except Exception as e:
            print(f"Error procesando {archivo.name}: {e}")

if __name__ == "__main__":
    carpeta_instancias = ruta_actual / "instances" / "ER"
    
    # Ejecutamos pidiendo 10 muestras con un límite máximo de 20 argumentos
    # (Si quieres forzar un umbral fijo, añade por ejemplo umbral_manual=0.25)
    ejecutar_muestras_aleatorias(carpeta_instancias, num_muestras=10, max_args=20)