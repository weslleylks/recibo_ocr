from backend.parser.extracao_taxi import dados_taxi
from backend.parser.extracao_uber import extrair_dados_uber

EXTRATORES = {
    "UBER": extrair_dados_uber,
    "TAXI": dados_taxi,
    "PADRAO": extrair_dados_uber,
}


def normalizar_tipo_documento(tipo_documento):
    if not tipo_documento:
        return None

    tipo_normalizado = tipo_documento.upper()
    if "UBER" in tipo_normalizado:
        return "UBER"
    if "TAXI" in tipo_normalizado:
        return "TAXI"
    return "PADRAO"


def detectar_tipo_documento(result):
    texto_completo = " ".join(
        word.value
        for page in result.pages
        for block in page.blocks
        for line in block.lines
        for word in line.words
    )

    for chave in EXTRATORES.keys():
        if chave in texto_completo.upper():
            return chave

    return "PADRAO"


def processar_documento(result, tipo_documento=None):
    tipo_detectado = normalizar_tipo_documento(tipo_documento) or detectar_tipo_documento(result)
    funcao_extracao = EXTRATORES[tipo_detectado]
    return funcao_extracao(result)