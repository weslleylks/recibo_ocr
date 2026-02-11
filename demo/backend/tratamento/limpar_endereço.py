import re

def limpar_endereco(texto):
    # 1. Converte para minúsculo
    texto = texto.lower()
    # 2. Remove "r." ou "rua " do início (comum em endereços)
    texto = re.sub(r'^(r\.|rua\s+)', '', texto)
    # 3. Remove tudo que não for letra ou número (pontuação, espaços, traços)
    texto = re.sub(r'[^a-z0-9]', '', texto)
    return texto