from PIL import Image, ImageDraw, ImageFont
import math
import os

def create_parvan_logo(output_dir):
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Background Squircle (Dark Tech background with border)
    # Draw rounded rectangle
    margin = 24
    radius = 110
    
    # Outer Glow / Border
    draw.rounded_rectangle(
        [margin-4, margin-4, size-margin+4, size-margin+4],
        radius=radius+4,
        fill=(11, 15, 25, 255),
        outline=(0, 245, 255, 180),
        width=5
    )
    
    # Deep Dark Tech Surface
    draw.rounded_rectangle(
        [margin, margin, size-margin, size-margin],
        radius=radius,
        fill=(8, 12, 20, 255)
    )

    # 2. Tech Grid lines (Subtle)
    for y in range(80, 440, 40):
        draw.line([(60, y), (452, y)], fill=(20, 32, 50, 80), width=1)
    for x in range(80, 440, 40):
        draw.line([(x, 80), (x, 432)], fill=(20, 32, 50, 80), width=1)

    # 3. Network Orbital Rings (Internet Waves)
    center = (256, 230)
    for r, opacity, w in [(170, 70, 2), (135, 110, 3), (100, 160, 3)]:
        bbox = [center[0]-r, center[1]-r, center[0]+r, center[1]+r]
        draw.arc(bbox, start=200, end=340, fill=(0, 245, 255, opacity), width=w)
        draw.arc(bbox, start=20, end=160, fill=(37, 99, 235, opacity), width=w)

    # 4. Stylized "P" Letter merged with High-Speed Download Arrow
    # Stem of P (Left vertical bar)
    stem_left = 160
    stem_top = 110
    stem_right = 205
    stem_bottom = 360
    draw.rounded_rectangle([stem_left, stem_top, stem_right, stem_bottom], radius=14, fill=(0, 245, 255, 255))

    # P-Loop (Right arc with gradient fill)
    loop_bbox = [170, 110, 350, 260]
    draw.pieslice(loop_bbox, start=270, end=90, fill=(37, 99, 235, 255))
    inner_bbox = [215, 150, 305, 220]
    draw.pieslice(inner_bbox, start=270, end=90, fill=(8, 12, 20, 255))

    # 5. Dynamic Download Chevrons (Turbo Speed Arrow pointing down inside/beside the P)
    # Arrow head pointing down
    arrow_pts = [
        (256, 380),  # tip
        (320, 300),  # right
        (285, 300),  # right inner
        (285, 240),  # shaft right
        (227, 240),  # shaft left
        (227, 300),  # left inner
        (192, 300)   # left
    ]
    draw.polygon(arrow_pts, fill=(0, 245, 255, 255))
    
    # Second smaller speed accent chevron below
    chev2 = [
        (256, 420),
        (295, 380),
        (280, 380),
        (256, 404),
        (232, 380),
        (217, 380)
    ]
    draw.polygon(chev2, fill=(16, 185, 129, 255))

    # 6. "PARVAN" Text at bottom
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except Exception:
        font = ImageFont.load_default()
    
    text = "PARVAN"
    # Draw centered text
    draw.text((180, 436), text, fill=(240, 245, 255, 230), font=font)

    # Save PNGs and ICO
    png_path = os.path.join(output_dir, "logo.png")
    ico_path = os.path.join(output_dir, "icon.ico")
    
    img.save(png_path, "PNG")
    
    # Multi-resolution ICO for Windows
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ico_path, format="ICO", sizes=sizes)
    
    print(f"Created: {png_path} and {ico_path}")

create_parvan_logo(r"C:\Users\V I S I O N\parvan-download-manager")
