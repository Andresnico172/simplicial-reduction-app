import sys
from pathlib import Path
import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt

# --- 1. INITIAL CONFIGURATION ---
st.set_page_config(
    page_title="Simplicial Reduction",
    page_icon="🧪",
    layout="wide"
)

ruta_actual = Path(__file__).resolve().parent
ruta_src = ruta_actual / "pygarg" / "src"

if str(ruta_src) not in sys.path:
    sys.path.insert(0, str(ruta_src))

try:
    import pygarg.dung.apx_parser
    import pygarg.dung.solver
    PYGARG_DISPONIBLE = True
except ImportError as e:
    PYGARG_DISPONIBLE = False
    st.error(f"Critical error importing pygarg: {e}")

st.title("🧪 Simplicial Reduction for AFs")
st.markdown("""
This application allows you to load Argumentation Framework (`.apx`) instances, 
visualize their topology, execute simplicial reduction to W-QBAF under different semantics, and analyze compression metrics.
""")

if not PYGARG_DISPONIBLE:
    st.warning("⚠️ The application has stopped because the pygarg library could not be loaded.")
    st.info("💡 Tip: Check that there are no folders named 'pygarg' in the root directory confusing Python.")
    st.stop()

# --- 2. SIDEBAR (CONTROLS) ---
st.sidebar.header("🎛️ Control Panel")

familia = st.sidebar.selectbox("Instance Family", ["ER", "BA", "WS"])
carpeta_familia = ruta_actual / "pygarg" / "exp" / "instances" / familia

if carpeta_familia.exists():
    archivos_apx = sorted(list(carpeta_familia.glob("*.apx")))
    nombres_archivos = [f.name for f in archivos_apx]
else:
    archivos_apx = []
    nombres_archivos = []

if not nombres_archivos:
    st.sidebar.warning(f"No .apx files found in {carpeta_familia}")
    archivo_seleccionado = None
else:
    seleccion_archivo = st.sidebar.selectbox("Instance", nombres_archivos)
    archivo_seleccionado = carpeta_familia / seleccion_archivo

st.sidebar.markdown("---")

diccionario_semanticas = {
    "CF": "Conflict-Free (CF)",
    "CO": "Complete (CO)",
    "PR": "Preferred (PR)",
    "GR": "Grounded (GR)",
    "ID": "Ideal (ID)"
}
semantica_clave = st.sidebar.selectbox(
    "Argumentation Semantics", 
    options=list(diccionario_semanticas.keys()), 
    format_func=lambda x: diccionario_semanticas[x],
    index=1,
    key="selector_semantica"
)

modo_umbral = st.sidebar.radio("Pruning Threshold Criterion", ["Dynamic (Mean)", "Manual"])
umbral_manual = None
if modo_umbral == "Manual":
    umbral_manual = st.sidebar.slider(r"Threshold Value ($w \ge \mu$)", 0.0, 1.0, 0.1, 0.05)


# --- 3. PROCESSING LOGIC ---
def reduccion_simplicial_maximal(args, atts, semantica, umbral_manual=None):
    import statistics
    
    # 1. Get raw extensions from the solver
    extensiones = list(pygarg.dung.solver.extension_enumeration(args, atts, semantica))
    num_extensiones_brutas = len(extensiones)
    
    # 2. Clean and find maximals (Facets)
    facetas_todas = [set(ext) for ext in extensiones if ext]
    facetas = [f for f in facetas_todas if not any(f < g for g in facetas_todas if f != g)]
    num_facetas = len(facetas)
    
    A_star_inicial = {f"X_{i+1}": set(faceta) for i, faceta in enumerate(facetas)}
    
    out_adj = {arg: set() for arg in args}
    in_adj = {arg: set() for arg in args}
    for atacante, atacado in atts:
        out_adj[atacante].add(atacado)
        in_adj[atacado].add(atacante)

    pesos_brutos = {}
    for id_X, X in A_star_inicial.items():
        for id_Y, Y in A_star_inicial.items():
            if id_X == id_Y: continue
            atacantes = {x for x in X if not out_adj[x].isdisjoint(Y)}
            if atacantes:
                pesos_brutos[(id_X, id_Y)] = len(atacantes) / len(X)
                
    if not pesos_brutos:
        umbral_aplicado = 0.0
    elif umbral_manual is not None:
        umbral_aplicado = umbral_manual
    else:
        umbral_aplicado = statistics.mean(pesos_brutos.values())
        
    R_star_filtrado = []
    pesos_w_finales = {}
    nodos_conectados = set()
    
    for (origen, destino), peso in pesos_brutos.items():
        if peso >= umbral_aplicado:
            R_star_filtrado.append((origen, destino))
            pesos_w_finales[(origen, destino)] = peso
            nodos_conectados.add(origen)
            nodos_conectados.add(destino)
            
    A_star_conectados = {id_X: X for id_X, X in A_star_inicial.items() if id_X in nodos_conectados}
    A_star_aislados = {id_X: X for id_X, X in A_star_inicial.items() if id_X not in nodos_conectados}
    
    valoraciones_tau = {}
    for id_X, X in A_star_conectados.items():
        r_out = sum(len([tgt for tgt in out_adj[x] if tgt not in X]) for x in X)
        r_in = sum(len([src for src in in_adj[x] if src not in X]) for x in X)
        if (r_out + r_in) == 0:
            valoraciones_tau[id_X] = 0.5
        else:
            valoraciones_tau[id_X] = 0.5 * (((r_out - r_in) / (r_out + r_in)) + 1.0)
            
    for id_X in A_star_aislados.keys():
        valoraciones_tau[id_X] = 0.5
            
    return A_star_conectados, A_star_aislados, R_star_filtrado, pesos_w_finales, valoraciones_tau, umbral_aplicado, num_extensiones_brutas, num_facetas


# --- 4. MAIN BODY AND UI ---
if archivo_seleccionado and archivo_seleccionado.exists():
    args, atts = pygarg.dung.apx_parser.parse(str(archivo_seleccionado))
    
    # Visual feedback while evaluating
    with st.spinner(f"Evaluating topology under {semantica_clave} semantics..."):
        conectados, aislados, R_star, pesos_w, valoraciones_tau, umbral_usado, raw_ext, num_facetas = reduccion_simplicial_maximal(
            args, atts, semantica_clave, umbral_manual if modo_umbral == "Manual" else None
        )
    
    # Metrics breakdown
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Original Nodes", len(args))
    col2.metric(f"Raw Ext. ({semantica_clave})", raw_ext)
    col3.metric("Maximal Facets", num_facetas)
    
    total_reducidos = len(conectados) + len(aislados)
    col4.metric("W-QBAF Nodes", total_reducidos)
    col5.metric(r"Threshold ($\mu$)", f"{umbral_usado:.2f}")
    
    st.markdown("---")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "🌐 Original AF", 
        "🧠 Resulting W-QBAF", 
        "⚙️ Internal Details", 
        "📊 Performance"
    ])
    
    with tab1:
        st.subheader("Original Framework Topology")
        fig, ax = plt.subplots(figsize=(8, 6))
        G = nx.DiGraph()
        G.add_nodes_from(args)
        G.add_edges_from(atts)
        pos = nx.spring_layout(G, seed=42)
        nx.draw_networkx_nodes(G, pos, node_color='lightblue', node_size=700, edgecolors='black', ax=ax)
        nx.draw_networkx_labels(G, pos, font_size=12, font_weight='bold', ax=ax)
        nx.draw_networkx_edges(G, pos, edgelist=G.edges(), arrowstyle='-|>', arrowsize=20, edge_color='red', width=1.5, ax=ax)
        ax.axis("off")
        st.pyplot(fig)
        
    with tab2:
        st.subheader(f"Reduced Graph under {semantica_clave} semantics")
        
        if total_reducidos > 0:
            fig_red, ax_red = plt.subplots(figsize=(10, 7))
            G_red = nx.DiGraph()
            nodos_red = list(conectados.keys()) + list(aislados.keys())
            G_red.add_nodes_from(nodos_red)
            
            aristas_red = [(u, v) for (u, v) in R_star]
            G_red.add_edges_from(aristas_red)
            
            pos_red = nx.spring_layout(G_red, seed=84)
            nx.draw_networkx_nodes(G_red, pos_red, node_color='#bbf0b1', node_size=2500, edgecolors='#206312', ax=ax_red)
            
            labels_nodos = {nodo: f"{nodo}\nτ={valoraciones_tau[nodo]:.2f}" for nodo in nodos_red}
            nx.draw_networkx_labels(G_red, pos_red, labels=labels_nodos, font_size=10, font_weight='bold', ax=ax_red)
            
            if aristas_red:
                nx.draw_networkx_edges(G_red, pos_red, edgelist=aristas_red, arrowstyle='-|>', arrowsize=25, edge_color='#e85f5f', width=2.5, ax=ax_red)
                labels_aristas = {(u, v): f"{pesos_w[(u, v)]:.2f}" for u, v in aristas_red}
                nx.draw_networkx_edge_labels(G_red, pos_red, edge_labels=labels_aristas, font_size=9, font_color='red', ax=ax_red)
                
            ax_red.axis("off")
            st.pyplot(fig_red)
        else:
            st.error("💥 Total Collapse: The evaluation generated an empty graph (0 meta-arguments) under this semantics.")

    with tab3:
        st.subheader("W-QBAF Breakdown")
        st.write(f"**Connected Meta-arguments:** {len(conectados)}")
        st.json({k: list(v) for k, v in conectados.items()})
        
        st.write(f"**Isolated Meta-arguments ($\tau = 0.5$):** {len(aislados)}")
        st.json({k: list(v) for k, v in aislados.items()})
        
        st.write("**Filtered Attack Weights ($w$):**")
        if pesos_w:
            tabla_pesos = [{"Source": k[0], "Target": k[1], "Weight ($w$)": v} for k, v in pesos_w.items()]
            st.dataframe(tabla_pesos, use_container_width=True)
        else:
            st.info("No attack edges exceeded the selected threshold.")
        
    with tab4:
        st.subheader("Compression Analysis")
        compresion_porcentaje = (total_reducidos / len(args)) * 100 if len(args) > 0 else 0
        st.progress(min(compresion_porcentaje / 100.0, 1.0))
        st.write(f"The reduced graph represents **{compresion_porcentaje:.1f}%** of the original graph's size.")
        
        if compresion_porcentaje > 100:
            st.error("⚠️ Combinatorial Explosion detected: The simplicial complex is larger than the original graph.")
        elif compresion_porcentaje == 0:
            st.error("⚠️ Structural Collapse: No admissible coalition survived.")
        else:
            st.success("✅ Successful compression achieved.")
else:
    st.info("Please select a valid file from the sidebar.")