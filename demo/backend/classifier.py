from backend.parser.extracao_taxi import dados_taxi
from backend.parser.extracao_uber import extrair_dados_uber
from backend.parser.extracao_nf import dados_nf

def processar_documento(result):
    # Mapeamento de Extratores
    EXTRATORES = {
        'UBER': extrair_dados_uber,
        'TAXI': dados_taxi,
        'PADRAO': extrair_dados_uber, # Caso não identifique nenhum
        'NF': dados_nf
    }
    # 1. Identificação (Classificador)
    texto_completo = " ".join([word.value for page in result.pages for block in page.blocks for line in block.lines for word in line.words])
    tipo_detectado = 'PADRAO'
    for chave in EXTRATORES.keys():
        if chave in texto_completo.upper():
            tipo_detectado = chave
            break
            
    # 2. Execução da estratégia correta
    funcao_extracao = EXTRATORES[tipo_detectado]
    return funcao_extracao(result)