from pdf2image import convert_from_bytes
import cv2
import numpy as np

def redimensionar_inteligente(image, largura_alvo=2000):
    (h, w) = image.shape[:2]
    
    if w >= largura_alvo:
        return image
    
    proporcao = largura_alvo / float(w)
    altura_alvo = int(h * proporcao)
    
    imagem_redimensionada = cv2.resize(image, (largura_alvo, altura_alvo), 
                                     interpolation=cv2.INTER_CUBIC)
    
    # GARANTIA: Remove ruídos de interpolação e garante formato de memória contíguo
    imagem_redimensionada = np.clip(imagem_redimensionada, 0, 255).astype(np.uint8)
    return np.ascontiguousarray(imagem_redimensionada)
    
def processar_pdf_com_clahe(uploaded_file):
    # caminho_poppler = "C:/Users/bp569094/OneDrive - bpsplicencas.onmicrosoft.com/Área de Trabalho/poppler/poppler-25.12.0/Library/bin"

    uploaded_file.seek(0)
    file_bytes = uploaded_file.read()

    # 1. Converter PDF para lista de imagens (uma por página)
    # Recomendo 300 DPI para garantir qualidade no texto escrito à mão
    paginas = convert_from_bytes(
        file_bytes, 
        dpi=300,
        # poppler_path=caminho_poppler
    )

    imagens_processadas = []
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    for pagina in paginas:
        # 2. Converter imagem do PIL para formato OpenCV (BGR -> Gray)
        img_np = np.array(pagina)

        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

        img_redimensionada = redimensionar_inteligente(gray)
        # 3. Aplicar o CLAHE
        img_final = clahe.apply(img_redimensionada)
        
        imagens_processadas.append(img_final)

    return imagens_processadas

