#%%
from backend.tratamento.formatar_data import formatar_data_ocr
# from projeto_ocr.formatar_data import 
import re
import numpy as np
from backend.tratamento.correcao_numeros import corrigir_numeros

def dados_taxi(result):
    datas = []
    valor = []
    empresa = []
    local_ida = []
    local_volta = []

    # Variável de controle para não repetir a empresa
    empresa_identificada = False

    dic_endereços = {
        'BP': 'Maestro Cardim, 769',
        'Aeroporto': ['Washington Luís', 'Hélio Smidt', 'Aeroporto de guarulhos', 'Aeroporte de congonhas', 'Aeroporto de cumbica', 'Aeroporto de viracopos', 'Rod. Santos Dumont, km 66']
    }

    # Regex patterns
    # Melhorado para aceitar espaços e variações comuns
    pattern_data = r'(\d+ de \w{3}. de \d{4})' 
    pattern_valor = r'[RS5]?[RZ2$S][S\$:][: ]?([ZzIiSs12]?\d{1,3}[ZzIiSs12]?(\.\d{3})*([.,]\d{2})?)\b'
    pattern_empresa = r'(TAXI|taxi|Taxi)'
    pattern_itinerario = r'(?i)[rario]+?:(\w+)\s(\w+)'

    # Loop Único e Eficiente
    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                # 1. Texto da linha
                texto_da_linha = " ".join([word.value for word in line.words]).strip()

                if not empresa_identificada:
                    # 2. Busca de Empresa (Qualquer lugar da linha)
                    match_empresa = re.search(pattern_empresa, texto_da_linha)
                    if match_empresa:
                        empresa.append(match_empresa.group(1).upper()) # Padroniza para UBER
                        empresa_identificada = True # Bloqueia novas entradas de empresa

                # 3. Busca de Data (Padrão '6denov')
                if re.search(pattern_data, texto_da_linha):
                    data_formatada = formatar_data_ocr(texto_da_linha)
                    if data_formatada:
                        datas.append(data_formatada)

                # 4. Busca de Valor por REGEX
                match_valor = re.search(pattern_valor, texto_da_linha)
                if match_valor:
                    val_limpo = corrigir_numeros(match_valor.group(1).replace(',', '.'))
                    valor.append(float(val_limpo))

                # 5. Busca do itinerário por posição geométrica
                # Verificamos se a linha está dentro da caixa que você definiu
                match_itinerario = re.search(pattern_itinerario, texto_da_linha)
                if match_itinerario:
                    local_ida.append(match_itinerario.group(1).upper())
                    local_volta.append(match_itinerario.group(2).upper())

    return datas, valor, empresa, local_ida, local_volta