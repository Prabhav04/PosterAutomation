from PIL import Image, ImageDraw, ImageFont
import os


text = "ഇത് മലയാളം ടെക്സ്റ്റ് ആണ്."
font_path = os.path.join("fonts", "Manjari-Bold.ttf")
font = ImageFont.truetype(font_path, 48)

img = Image.new("RGB", (1000, 300), color="white")
draw = ImageDraw.Draw(img)
draw.text((50, 100), text, font=font, fill="black")

img.save("test_malayalam_output.jpg")
print("✅ Saved test_malayalam_output.jpg")
