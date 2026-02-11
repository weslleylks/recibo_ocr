from backend.tratamento.normalizar import limpeza_total
from thefuzz import fuzz

def buscar_chave (dicionário, busca):
    busca_limpa = limpeza_total(busca)

    for key, value in dicionário.items():
        if  isinstance(value, list):
            for item in value:
                if fuzz.partial_ratio(busca_limpa, limpeza_total(item)) >= 90:
                    return key

        elif isinstance(value, str):
            if fuzz.partial_ratio(busca_limpa, limpeza_total(value)) >= 90:
                return key

        return 'Local não identificado'