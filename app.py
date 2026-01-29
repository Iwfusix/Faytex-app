import streamlit as st
import pandas as pd
import math
from PIL import Image
import base64

# ==========================================
# 1. CONFIGURACIÓN Y ESTILOS
# ==========================================
st.set_page_config(
    page_title="Faytex Estructuras",
    page_icon="🏗️",
    layout="centered"
)

# Estilos CSS para ocultar marcas de agua y mejorar tablas
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp {background-color: white;}
    h1 {color: #0056b3;}
    div[data-testid="stExpander"] div[role="button"] p {font-size: 1.1rem; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. LÓGICA DE CÁLCULO (EXACTA A LA VERSIÓN DE ESCRITORIO)
# ==========================================

PARAMS_ASP = {
    "1": (0.17, 0.01, 1.0),
    "2": (0.19, 0.05, 2.0),
    "3": (0.19, 0.05, 2.0), # Rural Acc. (Mapeado a II según Excel usuario)
    "4": (0.22, 0.30, 5.0), # Urbana (Mapeado a III para obtener Ce=1.34 a 3m)
    "5": (0.24, 1.00, 10.0)
}

TABLA_CPE_A = {0:[0.5,-0.6,None,None],5:[0.8,-1.1,0.5,-0.7],10:[1.2,-1.5,0.6,-0.8],15:[1.4,-1.8,0.6,-0.8],20:[1.7,-2.2,0.8,-0.9],25:[2.0,-2.6,None,None],30:[2.2,-3.0,None,None]}
TABLA_CPE_B = {0:[1.8,-1.3,None,None],5:[2.1,-1.7,1.5,-1.3],10:[2.4,-2.0,1.4,-1.3],15:[2.7,-2.4,1.5,-1.3],20:[2.9,-2.8,1.6,-1.3],25:[3.1,-3.2,None,None],30:[3.2,-3.8,None,None]}
TABLA_CPE_C = {0:[1.1,-1.4,None,None],5:[1.3,-1.8,0.8,-1.6],10:[1.6,-2.1,0.8,-1.5],15:[1.8,-2.5,0.7,-1.6],20:[2.1,-2.9,0.6,-1.6],25:[2.3,-3.2,None,None],30:[2.4,-3.6,None,None]}

ALTURAS_NIEVE = [0, 200, 400, 500, 600, 700, 800, 900, 1000, 1200, 1400, 1600, 1800, 2200]
TABLA_NIEVE = {
    1:[0.3,0.5,0.6,0.7,0.9,1.0,1.2,1.4,1.7,2.3,3.2,4.3,None,None],
    2:[0.4,0.5,0.6,0.7,0.9,1.0,1.1,1.3,1.5,2.0,2.6,3.5,4.6,8.0],
    3:[0.2,0.2,0.2,0.3,0.3,0.4,0.5,0.6,0.7,1.1,1.7,2.6,4.0,None],
    4:[0.2,0.2,0.3,0.4,0.5,0.6,0.8,1.0,1.2,1.9,3.0,4.6,None,None],
    5:[0.2,0.3,0.4,0.4,0.5,0.6,0.7,0.8,0.9,1.3,1.8,2.5,None,None],
    6:[0.2,0.2,0.2,0.3,0.4,0.5,0.7,0.9,1.2,2.0,3.3,5.5,9.3,None],
    7:[0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2,None]
}

def interpolar(x, x1, x2, y1, y2):
    if y1 is None or y2 is None: return 0.0
    return y1 + (x - x1) * (y2 - y1) / (x2 - x1)

def get_cp(tabla, pend, idx):
    grados = sorted(tabla.keys())
    if pend in grados: return tabla[pend][idx] if tabla[pend][idx] is not None else 0.0
    if pend < grados[0]: return tabla[grados[0]][idx] or 0.0
    if pend > grados[-1]: return tabla[grados[-1]][idx] or 0.0
    for i in range(len(grados)-1):
        g1, g2 = grados[i], grados[i+1]
        if g1 < pend < g2: return interpolar(pend, g1, g2, tabla[g1][idx], tabla[g2][idx])
    return 0.0

def get_nieve(zona, h):
    vals = TABLA_NIEVE.get(zona)
    if h <= 0: return vals[0]
    for i in range(len(ALTURAS_NIEVE)-1):
        h1, h2 = ALTURAS_NIEVE[i], ALTURAS_NIEVE[i+1]
        v1, v2 = vals[i], vals[i+1]
        if v2 is None: return v1
        if h1 <= h <= h2: return interpolar(h, h1, h2, v1, v2)
    return vals[-2]

def calcular_ce_correcto(z, grado_idx_str):
    idx = grado_idx_str.split(":")[0]
    k, L, Zmin = PARAMS_ASP.get(idx, (0.22, 0.3, 5.0))
    z_eff = max(z, Zmin)
    F = k * math.log(z_eff / L)
    Ce = F * (F + 7 * k)
    return Ce

# ==========================================
# 3. GENERADOR DE PDF (HTML)
# ==========================================
def obtener_html_informe(d, res, logo_b64):
    def c(l): return "".join([f"<td>{v}</td>" for v in l])
    
    # Insertar logo en base64 para que se vea al descargar
    img_tag = f'<img src="data:image/png;base64,{logo_b64}" style="height:60px;" alt="Logo">' if logo_b64 else "<h1>FAYTEX</h1>"

    html = f"""
    <html><head><title>Informe Faytex</title>
    <style>
        @page {{ size: A4 landscape; margin: 10mm; }}
        body {{ font-family: 'Segoe UI', Arial, sans-serif; -webkit-print-color-adjust: exact; padding: 10px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid #0056b3; padding-bottom: 10px; margin-bottom: 20px; }}
        h1 {{ margin: 0; color: #0056b3; font-size: 24px; }}
        .box {{ background: #f4f6f9; padding: 15px; margin-bottom: 20px; border: 1px solid #ddd; border-radius: 5px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 10px; table-layout: fixed; }}
        th, td {{ border: 1px solid #999; padding: 6px 2px; text-align: center; word-wrap: break-word; }}
        th {{ background-color: #0056b3 !important; color: white !important; font-weight: bold; }}
        tr:nth-child(even) td {{ background-color: #f2f2f2 !important; }}
        th:first-child, td:first-child {{ width: 140px; text-align: left; padding-left: 5px; font-weight: bold; }}
    </style></head><body>
    <div class="header">
        <div>
            <h1>FAYTEX ESTRUCTURAS</h1>
            <p style="margin:0; font-size:12px; color:#555">Informe Técnico de Cargas</p>
        </div>
        {img_tag}
    </div>

    <div class="box">
        <h3 style="margin-top:0; border-bottom:1px solid #ccc; padding-bottom:5px;">Datos del Proyecto</h3>
        <table style="border:none; width:100%;">
            <tr style="background:none;"><td style="border:none; text-align:left;">
                <b>Geometría:</b> {d['ancho']}m x {d['altura']}m (Pendiente {d['pend']}º)<br>
                <b>Separaciones:</b> Pórticos {d['sp']}m | Correas {d['sc']}m
            </td><td style="border:none; text-align:left;">
                <b>Ubicación:</b> Zona {d['zv']} | Aspereza {d['asp']} | Altitud {d['alt']}m<br>
                <b>Cargas Base:</b> Nieve {d['zn']} | Uso {d['uso']} kN/m²
            </td></tr>
        </table>
    </div>

    <h3 style="color:#333;">Tabla de Resultados</h3>
    <table>
        <thead>
            <tr>
                <th>Caso de Carga</th>
                <th colspan="3">V1 (Presión Simple)</th>
                <th colspan="3">V2 (Succión Simple)</th>
                <th colspan="3">V3 (Presión Doble)</th>
                <th colspan="3">V4 (Succión Doble)</th>
                <th style="background:#444 !important;">PP</th>
                <th style="background:#444 !important;">Nieve</th>
                <th style="background:#444 !important;">Uso</th>
            </tr>
            <tr>
                <th>Zona</th>
                <th>A</th><th>B</th><th>C</th>
                <th>A</th><th>B</th><th>C</th>
                <th>A</th><th>B</th><th>C</th>
                <th>A</th><th>B</th><th>C</th>
                <th>-</th><th>-</th><th>-</th>
            </tr>
        </thead>
        <tbody>
            <tr><td>Carga Superficial (kN/m²)</td>{c(res['sup'])}</tr>
            <tr><td>Carga Lineal Pórtico (kN/m)</td>{c(res['por'])}</tr>
            <tr><td>Carga Lineal Correa (kN/m)</td>{c(res['cor'])}</tr>
        </tbody>
    </table>

    <div style="margin-top:30px; font-size:9px; color:#777; border-top:1px solid #eee; padding-top:10px;">
        Cálculos realizados según normativa vigente (CTE/Eurocódigo). Ce={d['ce']:.3f}, qb={d['qb']:.3f}, Nieve={d['qn']:.3f}.<br>
        Documento generado automáticamente por Faytex Estructuras.
    </div>
    <script>window.onload = function() {{ window.print(); }}</script>
    </body></html>
    """
    return html

# ==========================================
# 4. INTERFAZ STREAMLIT
# ==========================================

# LOGO EN HEADER
col_l1, col_l2, col_l3 = st.columns([1, 4, 1])
logo_b64 = None
with col_l2:
    try:
        image = Image.open("logo.png")
        st.image(image, use_container_width=True)
        # Convertir a base64 para el reporte HTML
        with open("logo.png", "rb") as image_file:
            logo_b64 = base64.b64encode(image_file.read()).decode()
    except:
        st.title("FAYTEX ESTRUCTURAS")

st.markdown("---")

# INPUTS (Organizados en 3 columnas)
with st.expander("📝 INTRODUCIR DATOS", expanded=True):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Geometría")
        ancho = st.number_input("Ancho (m)", value=4.8)
        altura = st.number_input("Altura (m)", value=4.0)
        pend = st.number_input("Pendiente (º)", value=7.5)
        sep_port = st.number_input("Sep. Pórticos (m)", value=4.8)
        
    with col2:
        st.subheader("Estructura")
        sep_corr = st.number_input("Sep. Correas (m)", value=1.1)
        p_corr = st.number_input("Peso Correa (kg/m)", value=4.0)
        p_chapa = st.number_input("Peso Chapa (kg/m²)", value=6.0)
        uso = st.number_input("Uso (kN/m²)", value=0.4)
        
    with col3:
        st.subheader("Ubicación")
        zv_txt = st.selectbox("Zona Viento", ["A (26 m/s)", "B (27 m/s)", "C (29 m/s)"], index=2)
        asp_txt = st.selectbox("Aspereza", ["1: Borde Mar", "2: Rural Llano", "3: Rural Accid.", "4: Urbana", "5: Centro"], index=3) # Default Urbana (4)
        zn_val = st.selectbox("Zona Nieve", [1,2,3,4,5,6,7], index=6)
        alt = st.number_input("Altitud (m)", value=100.0, step=50.0)

# BOTÓN CALCULAR
if st.button("⚡ CALCULAR CARGAS", type="primary", use_container_width=True):
    
    # --- CÁLCULOS ---
    mapa_v = {"A (26 m/s)": 26, "B (27 m/s)": 27, "C (29 m/s)": 29}
    vb = mapa_v.get(zv_txt, 29)
    qb = (0.5 * 1.25 * (vb**2)) / 1000.0

    Ce = calcular_ce_correcto(altura, asp_txt)
    qn = get_nieve(zn_val, alt)
    pp = ((p_corr / sep_corr) + p_chapa) * 0.00981

    vals_wind = []
    for idx in range(4): # V1, V2, V3, V4
        cpa = get_cp(TABLA_CPE_A, pend, idx)
        cpb = get_cp(TABLA_CPE_B, pend, idx)
        cpc = get_cp(TABLA_CPE_C, pend, idx)
        vals_wind.extend([qb * Ce * cpa, qb * Ce * cpb, qb * Ce * cpc])
        
    vals_est = [pp, qn, uso]
    
    def fmt(l): return [f"{x:.3f}" for x in l]
    row_sup = fmt(vals_wind + vals_est)
    row_por = fmt([x * sep_port for x in vals_wind] + [x * sep_port for x in vals_est])
    row_cor = fmt([x * sep_corr for x in vals_wind] + [x * sep_corr for x in vals_est])

    # --- RESULTADOS EN PANTALLA ---
    st.success(f"✅ Cálculo OK: Ce={Ce:.3f} | qb={qb:.3f} | Nieve={qn:.3f}")
    
    # Crear DataFrame para visualización limpia
    cols = ["V1-A", "V1-B", "V1-C", "V2-A", "V2-B", "V2-C", "V3-A", "V3-B", "V3-C", "V4-A", "V4-B", "V4-C", "PP", "Nieve", "Uso"]
    df = pd.DataFrame([row_sup, row_por, row_cor], columns=cols)
    df.insert(0, "Carga", ["Superficial (kN/m²)", "Lin. Pórtico (kN/m)", "Lin. Correa (kN/m)"])
    
    st.dataframe(df, use_container_width=True, hide_index=True)

    # --- GENERAR INFORME PDF (HTML) ---
    datos_dict = {
        'ancho':ancho, 'altura':altura, 'pend':pend, 'sp':sep_port, 'sc':sep_corr, 'zv':zv_txt, 'asp':asp_txt, 'zn':zn_val, 'alt':alt, 'uso':uso, 'qb':qb, 'ce':Ce, 'qn':qn
    }
    res_dict = {'sup':row_sup, 'por':row_por, 'cor':row_cor}
    
    html_content = obtener_html_informe(datos_dict, res_dict, logo_b64)
    
    st.download_button(
        label="📄 DESCARGAR INFORME PARA IMPRIMIR",
        data=html_content,
        file_name="Informe_Faytex.html",
        mime="text/html",
        use_container_width=True
    )