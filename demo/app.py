# Copyright (C) 2021-2026, Mindee.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://opensource.org/licenses/Apache-2.0> for full license details.

import ssl
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
import torch
from backend.classifier import processar_documento
from backend.pre_processing import processar_pdf_com_clahe
from backend.pytorch import DET_ARCHS, RECO_ARCHS, load_predictor
from backend.relatorio_reembolso import relatorio

from doctr.io import DocumentFile

# Globally disable SSL certificate verification
ssl._create_default_https_context = ssl._create_unverified_context

ROOT_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_LOCAL = ROOT_DIR / "docs" / "Relatório de Reembolso.xlsx"

# Configuracoes pre-definidas para cada tipo de documento.
PRESETS = {
    "Padrao": {
        "det_arch": "db_resnet50",
        "reco_arch": "crnn_vgg16_bn",
        "assume_straight_pages": False,
        "straighten_pages": False,
        "disable_crop_orientation": False,
        "bin_thresh": 0.3,
        "box_thresh": 0.2,
        "erosion_iter": 0,
    },
    "Uber (Digital)": {
        "det_arch": "db_resnet50",
        "reco_arch": "master",
        "assume_straight_pages": True,
        "straighten_pages": False,
        "disable_crop_orientation": True,
        "bin_thresh": 0.35,
        "box_thresh": 0.25,
        "erosion_iter": 0,
    },
    "Taxi (Manuscrito)": {
        "det_arch": "db_resnet50",
        "reco_arch": "master",
        "assume_straight_pages": False,
        "straighten_pages": False,
        "disable_crop_orientation": False,
        "bin_thresh": 0.26,
        "box_thresh": 0.2,
        "erosion_iter": 4,
    },
}

TIPOS_DOCUMENTO = list(PRESETS.keys())
EMPRESA_PADRAO_POR_TIPO = {
    "Uber (Digital)": "UBER",
    "Taxi (Manuscrito)": "TAXI",
    "Padrao": "PADRAO",
}

forward_device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


@st.cache_resource(show_spinner=False)
def carregar_predictor(
    det_arch: str,
    reco_arch: str,
    assume_straight_pages: bool,
    straighten_pages: bool,
    disable_crop_orientation: bool,
    bin_thresh: float,
    box_thresh: float,
):
    return load_predictor(
        det_arch=det_arch,
        reco_arch=reco_arch,
        assume_straight_pages=assume_straight_pages,
        straighten_pages=straighten_pages,
        export_as_straight_boxes=False,
        disable_page_orientation=False,
        disable_crop_orientation=disable_crop_orientation,
        bin_thresh=bin_thresh,
        box_thresh=box_thresh,
        device=forward_device,
    )


def chave_arquivo(uploaded_file, indice: int) -> str:
    return f"{indice}_{uploaded_file.name}_{uploaded_file.size}"


def normalizar_imagem_pdf(img: np.ndarray, iteracoes_erosao: int) -> bytes:
    if img.dtype != np.uint8:
        img = (img * 255).astype(np.uint8) if img.max() <= 1 else img.astype(np.uint8)

    img_denoised = cv2.fastNlMeansDenoising(img, None, 20, 7, 21)

    if iteracoes_erosao > 0:
        kernel = np.ones((2, 2), np.uint8)
        img_final = cv2.erode(img_denoised, kernel, iterations=iteracoes_erosao)
    else:
        img_final = img_denoised

    success, buffer = cv2.imencode(".jpg", img_final)
    if not success:
        raise ValueError("Erro no processamento da imagem.")

    return buffer.tobytes()


def carregar_documento(uploaded_file, preset: dict) -> list[np.ndarray]:
    uploaded_file.seek(0)
    nome_arquivo = uploaded_file.name.lower()

    if nome_arquivo.endswith(".pdf"):
        imagens_processadas = processar_pdf_com_clahe(uploaded_file)
        paginas = [
            normalizar_imagem_pdf(img, preset.get("erosion_iter", 0))
            for img in imagens_processadas
        ]
        if not paginas:
            raise ValueError("Nenhuma pagina encontrada no PDF.")
        return DocumentFile.from_images(paginas)

    return DocumentFile.from_images(uploaded_file.read())


def primeiro_valor(valores, padrao=None):
    return valores[0] if valores else padrao


def montar_linha_relatorio(nome_arquivo: str, tipo_documento: str, resultado) -> dict:
    datas, valores, empresas, locais_ida, locais_volta = resultado
    empresa = primeiro_valor(empresas) or EMPRESA_PADRAO_POR_TIPO[tipo_documento]

    return {
        "arquivo": nome_arquivo,
        "tipo": tipo_documento,
        "data": primeiro_valor(datas),
        "valor": primeiro_valor(valores),
        "empresa": empresa,
        "local_ida": primeiro_valor(locais_ida, ""),
        "local_volta": primeiro_valor(locais_volta, ""),
    }


def preparar_dados_relatorio(linhas: list[dict]) -> tuple[list, list, list, list, list]:
    return (
        [linha["data"] for linha in linhas],
        [linha["valor"] for linha in linhas],
        [linha["empresa"] for linha in linhas],
        [linha["local_ida"] for linha in linhas],
        [linha["local_volta"] for linha in linhas],
    )


def limpar_resultado_anterior(assinatura_uploads):
    if st.session_state.get("assinatura_uploads") == assinatura_uploads:
        return

    st.session_state["assinatura_uploads"] = assinatura_uploads
    st.session_state.pop("linhas_relatorio", None)
    st.session_state.pop("erros_processamento", None)
    st.session_state.pop("arquivo_excel", None)


def main(det_archs, reco_archs):
    st.set_page_config(layout="wide")
    st.title("Leitor de Recibos")

    st.sidebar.title("Importacao")
    uploaded_files = st.sidebar.file_uploader(
        "Selecione os comprovantes",
        type=["pdf", "png", "jpeg", "jpg"],
        accept_multiple_files=True,
    )
    uploaded_files = uploaded_files or []

    assinatura_uploads = tuple((file.name, file.size) for file in uploaded_files)
    limpar_resultado_anterior(assinatura_uploads)

    tipos_por_arquivo = {}
    if uploaded_files:
        with st.sidebar.expander("Tipo por documento", expanded=True):
            for indice, uploaded_file in enumerate(uploaded_files):
                chave = chave_arquivo(uploaded_file, indice)
                tipos_por_arquivo[chave] = st.selectbox(
                    uploaded_file.name,
                    TIPOS_DOCUMENTO,
                    key=f"tipo_documento_{chave}",
                )

    st.sidebar.markdown("---")
    st.sidebar.title("Ajuste fino")
    usar_ajuste_global = st.sidebar.checkbox(
        "Usar ajuste fino global para todos os arquivos",
        value=False,
    )

    ajustes_globais = {}
    if usar_ajuste_global:
        defaults = PRESETS["Padrao"]
        ajustes_globais = {
            "det_arch": st.sidebar.selectbox(
                "Modelo Deteccao",
                det_archs,
                index=det_archs.index(defaults["det_arch"]),
                key="det_arch_global",
            ),
            "reco_arch": st.sidebar.selectbox(
                "Modelo Reconhecimento",
                reco_archs,
                index=reco_archs.index(defaults["reco_arch"]),
                key="reco_arch_global",
            ),
            "assume_straight_pages": st.sidebar.checkbox(
                "Assumir pagina alinhada",
                value=defaults["assume_straight_pages"],
                key="assume_straight_pages_global",
            ),
            "straighten_pages": st.sidebar.checkbox(
                "Endireitar paginas (Deskew)",
                value=defaults["straighten_pages"],
                key="straighten_pages_global",
            ),
            "disable_crop_orientation": st.sidebar.checkbox(
                "Ignorar rotacao de palavras",
                value=defaults["disable_crop_orientation"],
                key="disable_crop_orientation_global",
            ),
            "bin_thresh": st.sidebar.slider(
                "Limiar de Binarizacao",
                0.1,
                0.9,
                defaults["bin_thresh"],
                key="bin_thresh_global",
            ),
            "box_thresh": st.sidebar.slider(
                "Limiar de Box",
                0.1,
                0.9,
                defaults["box_thresh"],
                key="box_thresh_global",
            ),
            "erosion_iter": st.sidebar.slider(
                "Nivel de Engrossamento (Erosao)",
                0,
                5,
                defaults["erosion_iter"],
                key="erosion_iter_global",
            ),
        }

    st.sidebar.markdown("---")
    analisar = st.sidebar.button(
        "Analisar documentos",
        type="primary",
        disabled=not uploaded_files,
    )

    cols = st.columns((1, 1))
    cols[0].subheader("Documentos anexados")
    cols[1].subheader("Resultado extraido")

    with cols[0]:
        if not uploaded_files:
            st.info("Selecione um ou mais comprovantes em PDF, PNG ou JPG.")
        else:
            indice_preview = st.selectbox(
                "Pre-visualizar documento",
                range(len(uploaded_files)),
                format_func=lambda indice: f"{indice + 1}. {uploaded_files[indice].name}",
            )
            arquivo_preview = uploaded_files[indice_preview]
            tipo_preview = tipos_por_arquivo[chave_arquivo(arquivo_preview, indice_preview)]
            preset_preview = ajustes_globais or PRESETS[tipo_preview]

            try:
                doc_preview = carregar_documento(arquivo_preview, preset_preview)
                pagina_preview = st.selectbox(
                    "Pagina",
                    range(len(doc_preview)),
                    format_func=lambda indice: str(indice + 1),
                )
                st.image(doc_preview[pagina_preview], caption=arquivo_preview.name)
            except Exception as exc:
                st.error(f"Nao foi possivel gerar a pre-visualizacao: {exc}")

            st.caption(f"{len(uploaded_files)} documento(s) selecionado(s).")

    if analisar:
        linhas_relatorio = []
        erros_processamento = []
        progresso = st.progress(0)

        with st.spinner("Carregando modelos e processando documentos..."):
            for indice, uploaded_file in enumerate(uploaded_files):
                chave = chave_arquivo(uploaded_file, indice)
                tipo_documento = tipos_por_arquivo[chave]
                preset = ajustes_globais or PRESETS[tipo_documento]

                try:
                    doc = carregar_documento(uploaded_file, preset)
                    predictor = carregar_predictor(
                        det_arch=preset["det_arch"],
                        reco_arch=preset["reco_arch"],
                        assume_straight_pages=preset["assume_straight_pages"],
                        straighten_pages=preset["straighten_pages"],
                        disable_crop_orientation=preset["disable_crop_orientation"],
                        bin_thresh=preset["bin_thresh"],
                        box_thresh=preset["box_thresh"],
                    )
                    # for num_pagina, pagina_img in enumerate(doc):
                    resultado = predictor(doc)
                    # st.write(f"**Análise da Página {num_pagina + 1}:**")
                    dados_extraidos = processar_documento(resultado, tipo_documento)
                    linhas_relatorio.append(
                        montar_linha_relatorio(
                            uploaded_file.name,
                            tipo_documento,
                            dados_extraidos,
                        )
                    )
                except Exception as exc:
                    erros_processamento.append(
                        {
                            "arquivo": uploaded_file.name,
                            "tipo": tipo_documento,
                            "erro": str(exc),
                        }
                    )

                progresso.progress((indice + 1) / len(uploaded_files))

        if linhas_relatorio:
            datas, valores, empresas, locais_ida, locais_volta = preparar_dados_relatorio(linhas_relatorio)
            arquivo_excel = relatorio(
                datas,
                valores,
                empresas,
                locais_ida,
                locais_volta,
                TEMPLATE_LOCAL,
            )

            st.session_state["linhas_relatorio"] = linhas_relatorio
            st.session_state["erros_processamento"] = erros_processamento
            st.session_state["arquivo_excel"] = arquivo_excel.getvalue()
        else:
            st.session_state["linhas_relatorio"] = []
            st.session_state["erros_processamento"] = erros_processamento
            st.session_state.pop("arquivo_excel", None)

    with cols[1]:
        linhas_relatorio = st.session_state.get("linhas_relatorio")
        erros_processamento = st.session_state.get("erros_processamento", [])
        arquivo_excel = st.session_state.get("arquivo_excel")

        if linhas_relatorio:
            st.success("Dados extraidos e planilha preparada.")
            st.dataframe(linhas_relatorio, hide_index=True, use_container_width=True)
            st.download_button(
                label="Baixar relatorio atualizado",
                data=arquivo_excel,
                file_name="Relatório de Reembolso.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        elif uploaded_files:
            st.info("Clique em Analisar documentos para gerar uma linha por comprovante.")

        if erros_processamento:
            st.warning("Alguns documentos nao puderam ser processados.")
            st.dataframe(erros_processamento, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main(DET_ARCHS, RECO_ARCHS)