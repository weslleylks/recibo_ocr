import re

def limpeza_total(texto):
    # Remove prefixos comuns, pontuação e espaços
    texto = texto.lower()
    texto = re.sub(r'^(r\.|rua\s+|av\.|avenida\s+)', '', texto)
    return re.sub(r'[^a-z0-9]', '', texto)