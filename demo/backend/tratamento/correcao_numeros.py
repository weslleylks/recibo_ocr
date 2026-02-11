def corrigir_numeros(texto):
    # Mapeamento de caracteres alfabéticos para seus equivalentes numéricos
    tabela = str.maketrans({
        'Z': '2', 'z': '2',
        'O': '0', 'o': '0',
        'S': '5', 's': '5',
        'I': '1', 'l': '1',
        'G': '6', 'b': '6',
        'B': '8'
    })
    return texto.translate(tabela)