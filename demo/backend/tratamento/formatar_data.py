import re

def formatar_data_ocr(texto_ocr): 
    # 2. Regex para separar o Dia do Mês
    # Procura por números no início e letras logo após
    match = re.match(r'(\d+) de (\w{3}). de (\w{4})', texto_ocr)
    
    if not match:
        return None
    
    dia = match.group(1)
    mes_texto = match.group(2)
    ano = match.group(3)

    # 3. Dicionário de meses (mapeamento por prefixo)
    meses_map = {
        'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04',
        'mai': '05', 'jun': '06', 'jul': '07', 'ago': '08',
        'set': '09', 'out': '10', 'nov': '11', 'dez': '12'
    }
    
    # Busca o mês pelo prefixo (ex: 'nov' ou 'denov')
    mes_num = None
    for chave, valor in meses_map.items():
        if chave in mes_texto:
            mes_num = valor
            break
            
    if not mes_num:
        return None
        
    # 4. Formatação Final (DD/MM/AAAA)
    dia_formatado = dia.zfill(2) # Transforma '6' em '06'
    return f"{dia_formatado}/{mes_num}/{ano}"