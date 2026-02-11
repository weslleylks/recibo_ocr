from backend.tratamento.formatar_data import formatar_data_ocr
from backend.tratamento.buscar_chave import buscar_chave
import re

def extrair_dados_uber(result):
    datas = []
    valor = []
    empresa = []
    local_ida = []
    local_volta = []

    # Variável de controle para não repetir a empresa
    empresa_identificada = False

    x_val_min, y_val_min = 0.76, 0.20
    x_val_max, y_val_max = 0.93, 0.25

    x_ida_min, y_ida_min = 0.13, 0.06
    x_ida_max, y_ida_max = 0.45, 0.09

    x_volta_min, y_volta_min = 0.13, 0.14
    x_volta_max, y_volta_max = 0.47, 0.17

    dic_endereços = {
        'BP': 'Maestro Cardim, 769',
        'Aeroporto': ['Washington Luís', 'Hélio Smidt', 'Aeroporto de guarulhos', 'Aeroporte de congonhas', 'Aeroporto de cumbica', 'Aeroporto de viracopos', 'Rod. Santos Dumont, km 66']
    }
    
    # Regex patterns
    # Melhorado para aceitar espaços e variações comuns
    pattern_data = r'(\d+ de \w{3}. de \d{4})' 
    pattern_valor = r'R\$\s?(\d+,\d{2})'
    pattern_empresa = r'(Uber|UBER|uber)'

    # Loop Único e Eficiente
    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                # 1. Geometria e Texto da Linha
                (x_min, y_min), (x_max, y_max) = line.geometry
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

                # 4. Busca de Valor por POSIÇÃO GEOMÉTRICA
                # Verificamos se a linha está dentro da caixa que você definiu
                if (x_min >= x_val_min and x_max <= x_val_max and 
                    y_min >= y_val_min and y_max <= y_val_max):
                    
                    match_v = re.search(pattern_valor, texto_da_linha)
                    if match_v:
                        # Limpeza: R$ 10,50 -> 10.50
                        val_limpo = match_v.group(1).replace(',', '.')
                        valor.append(float(val_limpo))

                # 5. Busca do endereço de IDA por posição geométrica
                # Verificamos se a linha está dentro da caixa que você definiu
                if (x_min >= x_ida_min and x_max <= x_ida_max and 
                    y_min >= y_ida_min and y_max <= y_ida_max):
                    
                    busca_local_ida = buscar_chave(dic_endereços, texto_da_linha)
                    local_ida.append(busca_local_ida)

                # 6. Busca do endereço de VOLTA por posição geométrica
                # Verificamos se a linha está dentro da caixa que você definiu
                if (x_min >= x_volta_min and x_max <= x_volta_max and 
                    y_min >= y_volta_min and y_max <= y_volta_max):

                    busca_local_volta = buscar_chave(dic_endereços, texto_da_linha)
                    local_volta.append(busca_local_volta)

    return datas, valor, empresa, local_ida, local_volta