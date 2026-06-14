import os
from PIL import Image, ImageDraw, ImageFont

def generate_app_icon_1024():
    width = 1024
    height = 1024
    
    # 1. Cria a imagem base transparente (RGBA)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    
    # Cria uma imagem de gradiente linear diagonal (Cyan #00f2fe para Pink #ff0050)
    c1 = (0, 242, 254)
    c2 = (255, 0, 80)
    gradient = Image.new("RGB", (width, height))
    for y in range(height):
        for x in range(width):
            t = (x + y) / (width + height)
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
            gradient.putpixel((x, y), (r, g, b))

    # --- DESENHO DO ÍCONE (MONITOR) ---
    # Máscara para o monitor
    icon_mask = Image.new("L", (width, height), 0)
    draw_icon = ImageDraw.Draw(icon_mask)
    
    # Coordenadas do monitor (Largura: 480, Altura: 320)
    # Centrado horizontalmente (x=512)
    # x0 = 512 - 240 = 272, x1 = 512 + 240 = 752
    # y0 = 120, y1 = 440
    m_x0, m_y0, m_x1, m_y1 = 272, 120, 752, 440
    stroke_w = 32
    
    # Borda do monitor (Retângulo arredondado)
    draw_icon.rounded_rectangle([m_x0, m_y0, m_x1, m_y1], radius=48, outline=255, width=stroke_w)
    
    # Triângulo do play (points: 13,9 13,19 22,14 no SVG original)
    # Proporcionalmente centralizado dentro do monitor (x=512, y=280)
    # Largura: ~120, Altura: ~140
    # Esquerda: x=465, Direita: x=585, Topo: y=210, Base: y=350
    draw_icon.polygon([(465, 210), (465, 350), (585, 280)], fill=255)
    
    # Suporte do monitor:
    # Linha vertical (Stand): do centro da base do monitor (512, 440) para a base (512, 510)
    draw_icon.line([(512, 440), (512, 510)], fill=255, width=stroke_w)
    draw_icon.ellipse([512 - stroke_w//2, 440 - stroke_w//2, 512 + stroke_w//2, 440 + stroke_w//2], fill=255)
    draw_icon.ellipse([512 - stroke_w//2, 510 - stroke_w//2, 512 + stroke_w//2, 510 + stroke_w//2], fill=255)
    
    # Linha horizontal (Base): de x=380 a x=644 em y=510
    draw_icon.line([(380, 510), (644, 510)], fill=255, width=stroke_w)
    draw_icon.ellipse([380 - stroke_w//2, 510 - stroke_w//2, 380 + stroke_w//2, 510 + stroke_w//2], fill=255)
    draw_icon.ellipse([644 - stroke_w//2, 510 - stroke_w//2, 644 + stroke_w//2, 510 + stroke_w//2], fill=255)
    
    # Cola o gradiente na imagem final usando a máscara do ícone
    img.paste(gradient, (0, 0), mask=icon_mask)
    
    # --- DESENHO DO TEXTO (POST RECAP) ---
    # Busca fontes do sistema (preferencialmente Segoe UI Bold para visual moderno e limpo)
    font_path = "C:\\Windows\\Fonts\\segoeuib.ttf"
    if not os.path.exists(font_path):
        font_path = "C:\\Windows\\Fonts\\arialbd.ttf"
        
    font_size = 140
    font = ImageFont.truetype(font_path, font_size)
    
    # 1. Renderiza o texto "Post" (Branco #FFFFFF)
    draw_text = ImageDraw.Draw(img)
    post_text = "Post"
    # Obtém o tamanho da caixa de texto
    p_bbox = draw_text.textbbox((0, 0), post_text, font=font)
    p_width = p_bbox[2] - p_bbox[0]
    p_x = (width - p_width) // 2
    p_y = 580
    draw_text.text((p_x, p_y), post_text, fill=(255, 255, 255, 255), font=font)
    
    # 2. Renderiza o texto "Recap" usando a máscara do gradiente
    recap_text = "Recap"
    r_bbox = draw_text.textbbox((0, 0), recap_text, font=font)
    r_width = r_bbox[2] - r_bbox[0]
    r_height = r_bbox[3] - r_bbox[1]
    r_x = (width - r_width) // 2
    r_y = 740
    
    # Cria uma máscara separada para o texto "Recap"
    text_mask = Image.new("L", (width, height), 0)
    draw_mask = ImageDraw.Draw(text_mask)
    draw_mask.text((r_x, r_y), recap_text, fill=255, font=font)
    
    # Aplica o gradiente na máscara do texto "Recap"
    img.paste(gradient, (0, 0), mask=text_mask)
    
    # Salva a imagem na pasta public do frontend como app_icon_1024.png
    public_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "public")
    os.makedirs(public_dir, exist_ok=True)
    
    app_icon_path = os.path.join(public_dir, "app_icon_1024.png")
    img.save(app_icon_path, "PNG")
    print(f"[SUCCESS] Ícone do App 1024x1024 gerado em: {app_icon_path}")
    
    # Também gera a versão com fundo escuro oficial do app (#0a0a0f) por conveniência do review
    dark_img = Image.new("RGBA", (width, height), (10, 10, 15, 255))
    dark_img.paste(img, (0, 0), mask=img)
    
    app_icon_dark_path = os.path.join(public_dir, "app_icon_1024_dark.png")
    dark_img.save(app_icon_dark_path, "PNG")
    print(f"[SUCCESS] Ícone do App 1024x1024 com fundo escuro gerado em: {app_icon_dark_path}")

if __name__ == "__main__":
    generate_app_icon_1024()
