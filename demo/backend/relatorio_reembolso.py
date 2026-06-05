Hugging Face's logo
Hugging Face
Models
Datasets
Spaces
Buckets
new
Docs
Enterprise
Pricing

Website
Community
Solutions

Spaces:
weslleyls
/
reembolso


like
0

Logs
App
Files
Community
Settings
reembolso
/
demo
/
backend
/
relatorio_reembolso.py

weslleyls's picture
weslleyls
Update demo/backend/relatorio_reembolso.py
e92141d
verified
2 days ago
raw

Copy download link
history
blame
3.4 kB
from io import BytesIO

import openpyxl


def obter_item(valores, indice, padrao=None):
    return valores[indice] if indice < len(valores) else padrao


def linha_ocupada(aba, linha, colunas):
    return any(aba.cell(row=linha, column=coluna).value is not None for coluna in colunas)


def encontrar_categoria(empresa, dic_empresa):
    empresa_normalizada = (empresa or "").upper()

    for categoria, empresas in dic_empresa.items():
        if any(nome_empresa.upper() in empresa_normalizada for nome_empresa in empresas):
            return categoria

    return None


def montar_descricao(empresa, local_ida, local_volta):
    trecho = " - ".join(local for local in [local_ida, local_volta] if local)
    return f"{empresa} {trecho}".strip() if trecho else empresa


def relatorio(datas, valor, empresa, local_ida, local_volta, caminho_arquivo):
    dic_empresa = {
        "Transporte": ["UBER", "99", "TAXI"],
    }
    dic_contabil = {
        "Transporte": {
            "Resumo contábil": "Reembolso de Condução e Transporte PROADI SUS",
            "Conta contábil": "PR50060003",
        },
    }

    planilha_aberta = openpyxl.load_workbook(caminho_arquivo)
    aba = planilha_aberta["MATRIZ - Relat Despesas"]

    coluna_data_b = 2
    coluna_empresa_u = 21
    col_descricao_aa = 27
    coluna_classificacao_despesa_ao = 41
    col_cod_contabil_ar = 44
    coluna_data_au = 47
    colunas_preenchidas = [
        coluna_data_b,
        coluna_empresa_u,
        col_descricao_aa,
        coluna_classificacao_despesa_ao,
        col_cod_contabil_ar,
        coluna_data_au,
    ]

    linha_inicial = 30
    while linha_ocupada(aba, linha_inicial, colunas_preenchidas):
        linha_inicial += 1

    total_linhas = max(len(datas), len(valor), len(empresa), len(local_ida), len(local_volta))

    for indice in range(total_linhas):
        linha_atual = linha_inicial + indice
        data = obter_item(datas, indice)
        valor_item = obter_item(valor, indice)
        empresa_item = obter_item(empresa, indice, "")
        local_ida_item = obter_item(local_ida, indice, "")
        local_volta_item = obter_item(local_volta, indice, "")

        if data is not None:
            aba.cell(row=linha_atual, column=coluna_data_b, value=data)

        if valor_item is not None:
            aba.cell(row=linha_atual, column=coluna_data_au, value=valor_item)

        if empresa_item:
            aba.cell(row=linha_atual, column=coluna_empresa_u, value=empresa_item)

        categoria_encontrada = encontrar_categoria(empresa_item, dic_empresa)
        if categoria_encontrada:
            info_contabil = dic_contabil[categoria_encontrada]
            aba.cell(
                row=linha_atual,
                column=coluna_classificacao_despesa_ao,
                value=info_contabil["Resumo contábil"],
            )
            aba.cell(
                row=linha_atual,
                column=col_cod_contabil_ar,
                value=info_contabil["Conta contábil"],
            )

        descricao = montar_descricao(empresa_item, local_ida_item, local_volta_item)
        if descricao:
            aba.cell(row=linha_atual, column=col_descricao_aa, value=descricao)

    output = BytesIO()
    planilha_aberta.save(output)
    output.seek(0)
    return output