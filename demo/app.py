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

def parse_ranges_to_groups(ranges_str: str, n_pages: int) -> list[list[int]]:
    """
    Recebe '1-2,3,4-5' (1-based) e retorna [[0,1],[2],[3,4]] (0-based indices).
    Valida limites (1..n_pages) e ordena páginas em cada grupo na ordem original.
    Lança ValueError para formatos inválidos.
    """
    if not ranges_str:
        return []
    grupos = []
    for part in ranges_str.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            a_i, b_i = int(a), int(b)
            if a_i < 1 or b_i < a_i or b_i > n_pages:
                raise ValueError("Range fora dos limites")
            grupos.append(list(range(a_i - 1, b_i)))
        else:
            i = int(part)
            if i < 1 or i > n_pages:
                raise ValueError("Pagina fora dos limites")
            grupos.append([i - 1])
    return grupos

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
                # Para cada arquivo (dentro do for indice, uploaded_file in enumerate(uploaded_files))
                chave = chave_arquivo(uploaded_file, indice)

                # Modo de processamento: 'por_arquivo' | 'por_pagina' | 'grupos'
                modo_key = f"modo_{chave}"
                if modo_key not in st.session_state:
                    st.session_state[modo_key] = "por_arquivo"

                st.session_state[modo_key] = st.radio(
                    f"Modo: {uploaded_file.name}",
                    ("por_arquivo", "por_pagina", "grupos"),
                    index=("por_arquivo", "por_pagina", "grupos").index(st.session_state[modo_key]),
                    key=f"radio_{modo_key}",
                )
                
                tipos_por_arquivo[chave] = st.selectbox(
                    f"Tipo: {uploaded_file.name}",
                    TIPOS_DOCUMENTO,
                    index=0,
                    key=f"tipo_documento_{chave}",
                )

                # Se por_pagina: permitir escolher tipo por página (default = tipo do arquivo)
                if st.session_state[modo_key] == "por_pagina":
                    # garantir carregamento das imagens para saber quantas páginas existem
                    try:
                        _doc_tmp = carregar_documento(uploaded_file, PRESETS["Padrao"])  # só para contar páginas
                        tipos_por_pagina_key = f"tipos_por_pagina_{chave}"
                        default_tipo = tipos_por_arquivo.get(chave, TIPOS_DOCUMENTO[0])
                        if tipos_por_pagina_key not in st.session_state:
                            st.session_state[tipos_por_pagina_key] = [st.selectbox(
                                f"Tipo página {i+1} ({uploaded_file.name})",
                                TIPOS_DOCUMENTO,
                                index=TIPOS_DOCUMENTO.index(default_tipo),
                                key=f"{tipos_por_pagina_key}_{i}",
                            ) for i in range(len(_doc_tmp))]
                            # re-render selects (Streamlit exige gerar selects; mantemos valores existentes)
                            tipos_existentes = st.session_state[tipos_por_pagina_key]
                            novos = []
                            for i in range(len(_doc_tmp)):
                                default = tipos_existentes[i] if i < len(tipos_existentes) else TIPOS_DOCUMENTO[0]
                                sel = st.selectbox(
                                    f"Tipo página {i+1} ({uploaded_file.name})",
                                    TIPOS_DOCUMENTO,
                                    index=TIPOS_DOCUMENTO.index(default),
                                    key=f"{tipos_por_pagina_key}_{i}",
                                )
                                novos.append(sel)
                            st.session_state[tipos_por_pagina_key] = novos
                    except Exception:
                        st.warning(f"Não foi possível obter páginas para {uploaded_file.name} no momento.")

                # Se grupos: permitir especificar ranges e escolher tipo por grupo
                if st.session_state[modo_key] == "grupos":
                    grupos_key = f"grupos_{chave}"
                    grupos_ranges = st.text_input(
                        f"Defina grupos (ex: 1-2,3,4-5) para {uploaded_file.name}",
                        value=st.session_state.get(grupos_key, ""),
                        key=f"input_{grupos_key}",
                    )
                    st.session_state[grupos_key] = grupos_ranges
                    # parse e mostrar selects por grupo (apenas visual/definição)
                    # parsing será validado no processamento; aqui apenas mostramos selects se conseguirmos parsear
                    try:
                        _doc_tmp = carregar_documento(uploaded_file, PRESETS["Padrao"])
                        n_pages = len(_doc_tmp)
                        grupos_list = parse_ranges_to_groups(grupos_ranges, n_pages)  # função auxiliar (ver abaixo)
                        tipos_por_grupo_key = f"tipos_por_grupo_{chave}"
                        if tipos_por_grupo_key not in st.session_state:
                            st.session_state[tipos_por_grupo_key] = [TIPOS_DOCUMENTO[0] for _ in grupos_list]
                        novos = []
                        for g_idx, grp in enumerate(grupos_list):
                            default = st.session_state[tipos_por_grupo_key][g_idx] if g_idx < len(st.session_state[tipos_por_grupo_key]) else TIPOS_DOCUMENTO[0]
                            sel = st.selectbox(
                                f"Tipo grupo {g_idx+1} (páginas {','.join(str(i+1) for i in grp)})",
                                TIPOS_DOCUMENTO,
                                index=TIPOS_DOCUMENTO.index(default),
                                key=f"{tipos_por_grupo_key}_{g_idx}_{chave}",
                            )
                            novos.append(sel)
                        st.session_state[tipos_por_grupo_key] = novos
                    except Exception:
                        st.info("Grupos inválidos ou sem páginas detectadas; corrija o formato.")

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
            tipo_preview = tipos_por_arquivo.get(chave_arquivo(arquivo_preview, indice_preview), TIPOS_DOCUMENTO[0])
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
                tipo_documento = tipos_por_arquivo.get(chave, TIPOS_DOCUMENTO[0])
                preset = ajustes_globais or PRESETS[tipo_documento]

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
                modo = st.session_state.get(f"modo_{chave}", "por_arquivo")

                if modo == "por_arquivo":
                    # agrega todas as páginas em uma linha (comportamento atual)
                    resultado = predictor(doc)
                    dados_extraidos = processar_documento(resultado, tipo_documento)
                    linhas_relatorio.append(montar_linha_relatorio(uploaded_file.name, tipo_documento, dados_extraidos))

                elif modo == "por_pagina":
                    tipos_por_pagina = st.session_state.get(f"tipos_por_pagina_{chave}", [tipo_documento] * len(doc))
                    for idx, pagina_img in enumerate(doc):
                        resultado_pagina = predictor(DocumentFile.from_images([pagina_img]))
                        dados_pagina = processar_documento(resultado_pagina, tipos_por_pagina[idx])
                        nome_pagina = f"{uploaded_file.name} - p{idx+1}"
                        linhas_relatorio.append(montar_linha_relatorio(nome_pagina, tipos_por_pagina[idx], dados_pagina))

                elif modo == "grupos":
                    grupos_ranges = st.session_state.get(f"grupos_{chave}", "").strip()
                    if not grupos_ranges:
                        grupos = [list(range(len(doc)))]
                    else:
                        grupos = parse_ranges_to_groups(grupos_ranges, len(doc))

                    tipos_por_grupo = st.session_state.get(f"tipos_por_grupo_{chave}", [])

                    for g_idx, grupo in enumerate(grupos):
                        pages_bytes = [doc[i] for i in grupo]
                        resultado_grupo = predictor(pages_bytes)
                        tipo_grp = tipos_por_grupo[g_idx] if g_idx < len(tipos_por_grupo) else tipo_documento
                        nome_grupo = f"{uploaded_file.name} - g{g_idx+1} (pags {','.join(str(i+1) for i in grupo)})"
                        dados_grupo = processar_documento(resultado_grupo, tipo_grp)
                        linhas_relatorio.append(montar_linha_relatorio(nome_grupo, tipo_grp, dados_grupo))

                progresso.progress((indice + 1) / len(doc))

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