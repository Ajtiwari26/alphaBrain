import sys
from pathlib import Path
from PIL import Image

def slice_image(img_path, cols, rows, out_pdf):
    img = Image.open(img_path)
    w, h = img.size
    slide_w = w // cols
    slide_h = h // rows
    
    images = []
    for r in range(rows):
        for c in range(cols):
            left = c * slide_w
            top = r * slide_h
            right = (c + 1) * slide_w
            bottom = (r + 1) * slide_h
            cropped = img.crop((left, top, right, bottom))
            if cropped.mode != 'RGB':
                cropped = cropped.convert('RGB')
            images.append(cropped)
            
    if len(images) > 11:
        images = images[:11]
        
    if images:
        images[0].save(out_pdf, save_all=True, append_images=images[1:], resolution=100.0)

if __name__ == "__main__":
    img_path = "/Users/ajaytiwari/.gemini/antigravity/brain/52fc9ef8-23aa-4045-a4de-2257c2c0a58f/.user_uploaded/media_1788283875111.jpg"
    slice_image(img_path, 3, 4, "/Users/ajaytiwari/Downloads/Sliced_ChatGPT_Slides_3x4.pdf")
