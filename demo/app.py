# # Copyright (C) 2021-2026, Mindee.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://opensource.org/licenses/Apache-2.0> for full license details.

import cv2
import numpy as np
import streamlit as st
import torch
from backend.pytorch import DET_ARCHS, RECO_ARCHS, load_predictor
from backend.pre_processing import processar_pdf_com_clahe
from backend.classifier import processar_documento
from backend.relatorio_reembolso import relatorio

from doctr.io import DocumentFile

# Configurações pré-definidas para cada tipo de documento
PRESETS = {
    "Padrao": {
        "det_arch": "db_resnet50",
        "reco_arch": "crnn_vgg16_bn",
        "assume_straight_pages": False,
        "straighten_pages": False,
        "disable_crop_orientation": False,
        "bin_thresh": 0.3,
        "box_thresh": 0.2,
        "erosion_iter": 0  # Sem erosão agressiva
    },
    "Uber (Digital)": {
        "det_arch": "db_resnet50",
        "reco_arch": "master", # Parseq é ótimo para digital
        "assume_straight_pages": True, # Digitais costumam ser retos
        "straighten_pages": False,
        "disable_crop_orientation": True, # Ganha velocidade
        "bin_thresh": 0.35,
        "box_thresh": 0.25,
        "erosion_iter": 0
    },
    "Taxi (Manuscrito)": {
        "det_arch": "db_resnet50",
        "reco_arch": "master", # Essencial para caligrafia
        "assume_straight_pages": False,
        "straighten_pages": False, # Tenta endireitar foto torta
        "disable_crop_orientation": False, # Verifica rotação de cada palavra
        "bin_thresh": 0.26, # Mais baixo para pegar traços finos
        "box_thresh": 0.2,
        "erosion_iter": 4 # Engrossar a letra (ajustado para não borrar demais)
    },
        "NF": {
        "det_arch": "db_resnet50",
        "reco_arch": "crnn_vgg16_bn",
        "assume_straight_pages": False,
        "straighten_pages": False,
        "disable_crop_orientation": False,
        "bin_thresh": 0.3,
        "box_thresh": 0.2,
        "erosion_iter": 0  # Sem erosão agressiva
    },
}

forward_device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

def main(det_archs, reco_archs):
    st.set_page_config(layout="wide")
    st.title("Leitor de Recibos")

    # --- 1. Inicialização do Session State ---
    # Isso garante que os valores existam antes dos widgets serem criados
    defaults = PRESETS["Padrao"]
    if "det_arch" not in st.session_state:
        for key, value in defaults.items():
            st.session_state[key] = value

    # Função para aplicar o preset quando o botão for clicado
    def apply_preset(name):
        preset = PRESETS[name]
        for key, value in preset.items():
            st.session_state[key] = value
        st.toast(f"Configuração '{name}' aplicada!", icon="✅")

    # --- 2. Barra Lateral: Botões de Ação Rápida ---
    st.sidebar.title("Tipo de Documento")
    col_b1, col_b2, col_b3, col_b4 = st.sidebar.columns(4)
    
    if col_b1.button("🚗 Uber"):
        apply_preset("Uber (Digital)")
        
    if col_b2.button("🚕 Táxi"):
        apply_preset("Taxi (Manuscrito)")
        
    if col_b3.button("📄 Padrão"):
        apply_preset("Padrao")

    if col_b4.button("NF"):
        apply_preset('NF')

    # --- 3. Upload e Processamento de Imagem ---
    st.sidebar.markdown("---")
    st.sidebar.title("Importação")
    uploaded_file = st.sidebar.file_uploader("Upload files", type=["pdf", "png", "jpeg", "jpg"])
    
    # Placeholders para as colunas
    cols = st.columns((1, 1))
    cols[0].subheader("Visualização")
    cols[1].subheader("Resultado Extraído")

    if uploaded_file is not None:
        # Lógica de processamento condicionada ao Preset (erosion_iter)
        if uploaded_file.name.endswith(".pdf"):
            imagem_processada = processar_pdf_com_clahe(uploaded_file)
            img = imagem_processada[0]

            if img.dtype != np.uint8:
                img = (img * 255).astype(np.uint8) if img.max() <= 1 else img.astype(np.uint8)

            # Aplica Denoise sempre
            img_denoised = cv2.fastNlMeansDenoising(img, None, 20, 7, 21)

            # Só aplica Erosão se o preset definir (ex: Taxi)
            iteracoes_erosao = st.session_state.get('erosion_iter', 0)
            if iteracoes_erosao > 0:
                kernel = np.ones((2,2), np.uint8)
                img_final = cv2.erode(img_denoised, kernel, iterations=iteracoes_erosao)
            else:
                img_final = img_denoised

            success, buffer = cv2.imencode(".jpg", img_final)
            if success:
                doc = DocumentFile.from_images(buffer.tobytes())
            else:
                st.error("Erro no processamento da imagem.")
        else:
            doc = DocumentFile.from_images(uploaded_file.read())

        # Mostra a imagem
        if doc:
            page_idx = st.sidebar.selectbox("Página", [idx + 1 for idx in range(len(doc))]) - 1
            page = doc[page_idx]
            # Exibe na coluna 0
            cols[0].image(page)

    # --- 4. Controles Manuais (Conectados ao Session State) ---
    st.sidebar.markdown("---")
    st.sidebar.title("Ajuste Fino")
    
    # Note o uso do argumento 'key'. Ele liga o widget ao session_state automaticamente.
    # Se o botão mudar o state, o widget atualiza visualmente.
    st.sidebar.selectbox("Modelo Detecção", det_archs, key="det_arch")
    st.sidebar.selectbox("Modelo Reconhecimento", reco_archs, key="reco_arch")
    
    st.sidebar.checkbox("Assumir página alinhada", key="assume_straight_pages")
    st.sidebar.checkbox("Endireitar páginas (Deskew)", key="straighten_pages")
    st.sidebar.checkbox("Ignorar rotação de palavras", key="disable_crop_orientation")
    
    st.sidebar.slider("Limiar de Binarização", 0.1, 0.9, key="bin_thresh")
    st.sidebar.slider("Limiar de Box", 0.1, 0.9, key="box_thresh")
    
    # Slider extra para controlar a erosão manualmente se quiser
    st.sidebar.slider("Nível de Engrossamento (Erosão)", 0, 5, key="erosion_iter")

    # --- 5. Botão de Análise ---
    st.sidebar.markdown("---")
    if st.sidebar.button("🔍 Analisar Página", type="primary"):
        if uploaded_file is None:
            st.warning("Por favor, faça o upload de um documento.")
        else:
            with st.spinner("Carregando modelos e processando..."):
                # Carrega o predictor usando os valores do Session State
                predictor = load_predictor(
                    det_arch=st.session_state.det_arch,
                    reco_arch=st.session_state.reco_arch,
                    assume_straight_pages=st.session_state.assume_straight_pages,
                    straighten_pages=st.session_state.straighten_pages,
                    export_as_straight_boxes=False, # Geralmente False é melhor para precisão
                    disable_page_orientation=False,
                    disable_crop_orientation=st.session_state.disable_crop_orientation,
                    bin_thresh=st.session_state.bin_thresh,
                    box_thresh=st.session_state.box_thresh,
                    device=forward_device
                )

                # Processamento OCR
                resultado = predictor([page])

                # Extração e Relatório
                datas, valor, empresa, local_ida, local_volta = processar_documento(resultado)

                # Exibe o resultado na coluna da direita
                with cols[1]:
                    # Define o caminho do template que está no seu GitHub
                    template_local = "docs/Relatório de Reembolso.xlsx"

                    # Executa o preenchimento e recebe o arquivo em memória
                    arquivo_excel = relatorio(datas, valor, empresa, local_ida, local_volta, template_local)

                    st.write(datas)
                    st.write(valor)
                    st.write(empresa)
                    st.write(local_ida)
                    st.write(local_volta)
                    
                    st.success("✅ Dados extraídos e planilha preparada!")

                    # Botão de Download
                    st.download_button(
                        label="📥 Baixar Relatório Atualizado",
                        data=arquivo_excel,
                        file_name="Relatório de Reembolso.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
if __name__ == "__main__":
    main(DET_ARCHS, RECO_ARCHS)