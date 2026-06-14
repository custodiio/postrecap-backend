import os
import math
from PIL import Image, ImageDraw

def generate():
    width = 512
    height = 512
    
    # 1. Cria a imagem de gradiente linear diagonal (Cyan #00f2fe para Pink #ff0050)
    # Cores RGB
    c1 = (0, 242, 254)
    c2 = (255, 0, 80)
    
    gradient = Image.new("RGB", (width, height))
    for y in range(height):
        for x in range(width):
            # Interpolação ao longo da diagonal
            t = (x + y) / (width + height)
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
            gradient.putpixel((x, y), (r, g, b))
            
    # 2. Cria a imagem de máscara (Grayscale) para desenhar o ícone
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    
    # Desenha o monitor/tela principal: rect x="2" y="4" width="28" height="20" rx="3"
    # Multiplicando por 16: x=32, y=64, w=448, h=320, rx=48. Linha = 32px
    # Em Pillow rounded_rectangle o box é [x0, y0, x1, y1]
    # x0=32, y0=64, x1=32+448=480, y1=64+320=384
    draw.rounded_rectangle([32, 64, 480, 384], radius=48, outline=255, width=32)
    
    # Desenha o triângulo de play: points="13,9 13,19 22,14" -> x=208, y=144; x=208, y=304; x=352, y=224
    draw.polygon([(208, 144), (208, 304), (352, 224)], fill=255)
    
    # Suporte do monitor:
    # Linha vertical: x1="16" y1="24" x2="16" y2="28" -> x0=256, y0=384, x1=256, y1=448. Espessura = 32
    # Linha horizontal: x1="12" y1="28" x2="20" y2="28" -> x0=192, y0=448, x1=320, y1=448. Espessura = 32
    # Para as pontas das linhas ficarem arredondadas (strokeLinecap="round" no SVG):
    # Desenhamos círculos (elipses) nas extremidades das linhas
    
    # Linha vertical
    draw.line([(256, 384), (256, 448)], fill=255, width=32)
    draw.ellipse([256 - 16, 384 - 16, 256 + 16, 384 + 16], fill=255)
    draw.ellipse([256 - 16, 448 - 16, 256 + 16, 448 + 16], fill=255)
    
    # Linha horizontal
    draw.line([(192, 448), (320, 448)], fill=255, width=32)
    draw.ellipse([192 - 16, 448 - 16, 192 + 16, 448 + 16], fill=255)
    draw.ellipse([320 - 16, 448 - 16, 320 + 16, 448 + 16], fill=255)
    
    # 3. Combina o gradiente com a máscara para criar o canal alfa transparente
    final_img = Image.new("RGBA", (width, height))
    final_img.paste(gradient, (0, 0), mask=mask)
    
    # 4. Salva o logo PNG na pasta public do frontend e também no backend
    public_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "public")
    os.makedirs(public_dir, exist_ok=True)
    
    logo_path = os.path.join(public_dir, "logo.png")
    final_img.save(logo_path, "PNG")
    print(f"[SUCCESS] Logo PNG gerado em: {logo_path}")
    
    # Também salva como favicon.png por conveniência
    favicon_path = os.path.join(public_dir, "favicon.png")
    final_img.save(favicon_path, "PNG")
    print(f"[SUCCESS] Favicon PNG gerado em: {favicon_path}")

if __name__ == "__main__":
    generate()
