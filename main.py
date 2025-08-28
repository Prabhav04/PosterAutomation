from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, ImageDraw, ImageFont
import os
import uuid
from datetime import datetime
import io
import requests
from typing import Optional
import re

app = FastAPI(title="Photo Template Backend", version="1.0.0")

# Configuration
DEFAULT_TEMPLATE_PATH = "public/template1.png"  # Default template
TEMPLATE_DIR = "public"  # Directory containing all templates
OUTPUT_DIR = "output"  # Directory to save processed images
FONTS_DIR = "fonts"  # Directory to store fonts
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff"}

# Maximum dimensions for resizing uploaded images
MAX_UPLOADED_WIDTH = 1000
MAX_UPLOADED_HEIGHT = 700

# Paths
ENGLISH_FONT_PATH = os.path.join(FONTS_DIR, "Inter_18pt-Bold.ttf")
MALAYALAM_FONT_PATH = os.path.join(FONTS_DIR, "Manjari-Bold.ttf")

# Constants
TEXT_Y_POSITION = 780
TEXT_FONT_SIZE = 40
TEXT_COLOR = (0, 0, 0)

# Create directories
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(FONTS_DIR, exist_ok=True)
os.makedirs(TEMPLATE_DIR, exist_ok=True)


def download_inter_font():
    """Download Inter Bold font if it doesn't exist."""
    if not os.path.exists(ENGLISH_FONT_PATH):
        try:
            font_url = "https://github.com/rsms/inter/raw/master/docs/font-files/Inter-Bold.ttf"
            response = requests.get(font_url)
            if response.status_code == 200:
                with open(ENGLISH_FONT_PATH, 'wb') as f:
                    f.write(response.content)
                print(f"Inter Bold downloaded to {ENGLISH_FONT_PATH}")
            else:
                print(f"Failed to download Inter font. Status: {response.status_code}")
        except Exception as e:
            print(f"Error downloading Inter font: {e}")


def download_malayalam_font():
    """Download Manjari Bold Malayalam font if it doesn't exist."""
    if not os.path.exists(MALAYALAM_FONT_PATH):
        try:
            font_url = "https://github.com/google/fonts/raw/main/ofl/manjari/Manjari-Bold.ttf"
            response = requests.get(font_url)
            if response.status_code == 200:
                with open(MALAYALAM_FONT_PATH, 'wb') as f:
                    f.write(response.content)
                print(f"Manjari Bold font downloaded to {MALAYALAM_FONT_PATH}")
            else:
                print(f"Failed to download Manjari font. Status: {response.status_code}")
        except Exception as e:
            print(f"Error downloading Manjari font: {e}")


def get_font(language: str = "en") -> ImageFont.FreeTypeFont:
    """
    Get the font object based on language.
    - "en": English (Inter)
    - "ml": Malayalam (Manjari)
    """
    if language == "ml":
        if not os.path.exists(MALAYALAM_FONT_PATH):
            download_malayalam_font()
        return ImageFont.truetype(MALAYALAM_FONT_PATH, TEXT_FONT_SIZE)

    # Default to Inter for English
    if not os.path.exists(ENGLISH_FONT_PATH):
        download_inter_font()
    return ImageFont.truetype(ENGLISH_FONT_PATH, TEXT_FONT_SIZE)


def get_text_color(template_path: str) -> tuple:
    """
    Get text color based on template.
    - Black (0, 0, 0) for default template and template1
    - White (255, 255, 255) for all other templates
    """
    template_name = os.path.basename(template_path)

    # Use black for default template or template1
    if template_name == os.path.basename(DEFAULT_TEMPLATE_PATH) or template_name == "template1.png":
        return (0, 0, 0)  # Black
    else:
        return (255, 255, 255)  # White


def parse_caption_and_template(text: str) -> tuple[str, str]:
    """
    Parse the text to extract template number and caption.

    Args:
        text: Input text in format "1-[caption]" or just "[caption]"

    Returns:
        tuple: (template_path, cleaned_caption)
    """
    if not text or not text.strip():
        return DEFAULT_TEMPLATE_PATH, ""

    # Pattern to match number-[caption] format
    pattern = r'^(\d+)-(.*)$'
    match = re.match(pattern, text.strip())

    if match:
        template_number = match.group(1)
        caption = match.group(2).strip()

        # Construct template filename
        template_filename = f"template{template_number}.png"
        template_path = os.path.join(TEMPLATE_DIR, template_filename)

        # Check if the template exists, fallback to default if not
        if os.path.exists(template_path):
            return template_path, caption
        else:
            print(f"Warning: Template {template_filename} not found, using default template")
            return DEFAULT_TEMPLATE_PATH, caption
    else:
        # No number prefix, use default template with full text as caption
        return DEFAULT_TEMPLATE_PATH, text.strip()


def get_available_templates() -> dict:
    """Get list of available templates in the template directory."""
    templates = {}

    # Add default template
    if os.path.exists(DEFAULT_TEMPLATE_PATH):
        templates["default"] = DEFAULT_TEMPLATE_PATH

    # Scan for numbered templates
    if os.path.exists(TEMPLATE_DIR):
        for file in os.listdir(TEMPLATE_DIR):
            if file.startswith("template") and file.endswith(".png"):
                # Extract number from filename like "template1.png"
                match = re.match(r'template(\d+)\.png', file)
                if match:
                    number = match.group(1)
                    templates[f"template{number}"] = os.path.join(TEMPLATE_DIR, file)

    return templates


def is_allowed_file(filename: str) -> bool:
    """Check if the uploaded file has an allowed extension."""
    return any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)


def resize_uploaded_image(image: Image.Image, max_width: int, max_height: int, min_width: int = 650) -> Image.Image:
    """
    Resize the uploaded image to fit within max dimensions (maintaining aspect ratio),
    but ensure the final width is at least `min_width` (upscale if needed).
    """
    original_width, original_height = image.size

    # First, scale down to fit within container
    width_ratio = max_width / original_width
    height_ratio = max_height / original_height
    scale_factor = min(width_ratio, height_ratio)

    new_width = int(original_width * scale_factor)
    new_height = int(original_height * scale_factor)

    resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Now check if final width is below minimum
    if new_width < min_width:
        upscale_ratio = min_width / new_width
        final_width = int(new_width * upscale_ratio)
        final_height = int(new_height * upscale_ratio)
        resized = resized.resize((final_width, final_height), Image.Resampling.LANCZOS)

    return resized


def detect_language(text: str) -> str:
    """Detect if text contains Malayalam characters."""
    for char in text:
        if '\u0D00' <= char <= '\u0D7F':  # Malayalam Unicode block
            return "ml"
    return "en"


def add_text_to_image(image: Image.Image, text: str, font: ImageFont.ImageFont,
                      text_color: tuple = (0, 0, 0)) -> Image.Image:
    """
    Adds horizontally centered, wrapped text to the image starting at a fixed Y position.
    The text box has a fixed width of 920px and a minimum height of 150px.
    The Y-position is respected as given, regardless of whether text height fits image or not.
    """
    TEXT_BOX_WIDTH = 920
    MIN_TEXT_BOX_HEIGHT = 150
    TEXT_Y_POSITION = 780  # <-- Your provided Y-coordinate

    draw = ImageDraw.Draw(image)

    # Word wrapping logic
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        test_bbox = draw.textbbox((0, 0), test_line, font=font)
        line_width = test_bbox[2] - test_bbox[0]

        if line_width <= TEXT_BOX_WIDTH:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    # Measure line height and total height of all lines
    line_height = font.getbbox("Ay")[3] - font.getbbox("Ay")[1]
    total_text_height = line_height * len(lines)
    text_box_height = max(MIN_TEXT_BOX_HEIGHT, total_text_height)

    # Start drawing text from the fixed y-position
    y = TEXT_Y_POSITION

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (image.width - text_width) // 2  # center horizontally
        draw.text((x, y), line, font=font, fill=text_color)
        y += line_height

    return image


def process_image(template_path: str, user_image: Image.Image, overlay_text: Optional[str] = None) -> str:
    """
    Process the user image and overlay the template on top.
    The uploaded image is resized to fit within max dimensions (830x590).
    Template maintains its original size and is overlaid on top.
    Optional text is added at specified position.
    Final image dimensions match the template.
    Returns the path to the saved processed image.
    """
    try:
        # Open the template image
        template = Image.open(template_path)

        # Get template dimensions (these will be the final image dimensions)
        template_width, template_height = template.size

        # Convert to RGB if necessary
        if user_image.mode != 'RGB':
            user_image = user_image.convert('RGB')

        # Resize user image to fit within max dimensions while maintaining aspect ratio
        resized_user_image = resize_uploaded_image(user_image, 613, 401, min_width=650)

        # Create a background canvas with template dimensions
        # Fill with white background (you can change this color if needed)
        background = Image.new('RGB', (template_width, template_height), (255, 255, 255))

        # Calculate position to center the resized user image on the template-sized canvas
        user_width, user_height = resized_user_image.size
        x = (template_width - user_width) // 2
        y = (template_height - user_height) // 2

        # Paste the resized user image onto the background
        background.paste(resized_user_image, (x, y))

        # Now overlay the template on top
        result = background.copy()

        # Check if template has transparency (alpha channel)
        if template.mode == 'RGBA' or 'transparency' in template.info:
            # Template has transparency, use it for proper overlay
            if template.mode != 'RGBA':
                template = template.convert('RGBA')

            # Paste template on top using alpha compositing
            result = result.convert('RGBA')
            result = Image.alpha_composite(result, template)
            result = result.convert('RGB')  # Convert back to RGB for JPEG saving
        else:
            # Template doesn't have transparency, direct paste
            result.paste(template, (0, 0))

        # Add text overlay if provided
        if overlay_text and overlay_text.strip():
            language = detect_language(overlay_text.strip())
            font = get_font(language=language)
            text_color = get_text_color(template_path)
            result = add_text_to_image(result, overlay_text.strip(), font, text_color)

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"processed_{timestamp}_{unique_id}.jpg"
        output_path = os.path.join(OUTPUT_DIR, filename)

        # Save the processed image
        result.save(output_path, "JPEG", quality=95)

        return output_path

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")


# Send processed image to web browser
app.mount("/output", StaticFiles(directory="output"), name="output")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    available_templates = get_available_templates()

    return {
        "message": "Photo Template Backend API",
        "version": "1.0.0",
        "endpoints": {
            "/process-image": "POST - Upload an image to overlay on template with optional text (English or Malayalam)",
            "/health": "GET - Health check and font/template availability",
            "/templates": "GET - List all available templates"
        },
        "caption_format": {
            "numbered": "Use format '1-Your caption text' to use template1.png",
            "default": "Use just 'Your caption text' to use default template",
            "examples": ["1-Beautiful sunset today!", "2-Amazing landscape view", "Just a regular caption"]
        },
        "available_templates": list(available_templates.keys()),
        "settings": {
            "max_uploaded_dimensions": f"{MAX_UPLOADED_WIDTH}x{MAX_UPLOADED_HEIGHT}",
            "layering": "Template overlays on top of uploaded image",
            "final_dimensions": "Match template dimensions",
            "text_position": f"Y: {TEXT_Y_POSITION}px (center aligned)",
            "text_font_size": TEXT_FONT_SIZE,
            "supported_fonts": {
                "english": "Inter Bold",
                "malayalam": "Manjari Bold"
            },
            "font_colors": {
                "default_template": "Black",
                "template1": "Black",
                "other_templates": "White"
            }
        }
    }


@app.get("/templates")
async def list_templates():
    """List all available templates."""
    available_templates = get_available_templates()

    template_info = {}
    for name, path in available_templates.items():
        template_info[name] = {
            "path": path,
            "exists": os.path.exists(path),
            "usage": f"{name.replace('template', '')}-[caption]" if name != "default" else "Just use [caption] without number prefix"
        }

    return {
        "available_templates": template_info,
        "total_count": len(available_templates),
        "usage_instructions": {
            "numbered_templates": "Use format 'N-[caption]' where N is the template number",
            "default_template": "Use just '[caption]' without number prefix",
            "examples": [
                "1-Beautiful sunset today!",
                "2-Amazing landscape view",
                "Just a regular caption"
            ]
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    default_template_exists = os.path.exists(DEFAULT_TEMPLATE_PATH)
    inter_font_exists = os.path.exists(ENGLISH_FONT_PATH)
    malayalam_font_exists = os.path.exists(MALAYALAM_FONT_PATH)
    available_templates = get_available_templates()

    return {
        "status": "healthy",
        "default_template_available": default_template_exists,
        "default_template_path": DEFAULT_TEMPLATE_PATH,
        "available_templates": available_templates,
        "template_count": len(available_templates),
        "fonts": {
            "english": {
                "available": inter_font_exists,
                "path": ENGLISH_FONT_PATH
            },
            "malayalam": {
                "available": malayalam_font_exists,
                "path": MALAYALAM_FONT_PATH
            }
        },
        "output_directory": OUTPUT_DIR,
        "max_uploaded_dimensions": f"{MAX_UPLOADED_WIDTH}x{MAX_UPLOADED_HEIGHT}",
        "final_dimensions": "Match template dimensions",
        "text_settings": {
            "position_y": TEXT_Y_POSITION,
            "font_size": TEXT_FONT_SIZE,
            "color": TEXT_COLOR,
            "language_support": ["en", "ml"]
        }
    }


@app.post("/process-image")
async def process_uploaded_image(
        file: UploadFile = File(...),
        text: Optional[str] = Form(None)
):
    """
    Process an uploaded image and overlay the appropriate template on top with optional text.

    Text format:
    - "1-Your caption" -> Uses template1.png with "Your caption" as text (BLACK font)
    - "2-Your caption" -> Uses template2.png with "Your caption" as text (WHITE font)
    - "Your caption" -> Uses default template with "Your caption" as text (BLACK font)

    Uploaded image is resized to max dimensions while maintaining aspect ratio.
    Template maintains original size and is overlaid on top.
    Text is added at specified position with language detection.
    Final image dimensions match the selected template.

    Args:
        file: Uploaded image file
        text: Optional text with optional template number prefix (e.g., "1-Caption text")

    Returns:
        JSON response with the path to the processed image
    """

    # Parse template and caption from text
    if text:
        template_path, caption = parse_caption_and_template(text)
        template_name = os.path.basename(template_path)
        print(f"Using template: {template_name}")
        print(f"Caption: {caption}")
    else:
        template_path = DEFAULT_TEMPLATE_PATH
        caption = ""
        template_name = os.path.basename(DEFAULT_TEMPLATE_PATH)

    print(f"Processing file: {file.filename}")

    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        if not is_allowed_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Supported formats: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Check if selected template exists
        if not os.path.exists(template_path):
            raise HTTPException(
                status_code=500,
                detail=f"Template image not found at {template_path}"
            )

        # Read the uploaded file
        contents = await file.read()

        # Open the image
        user_image = Image.open(io.BytesIO(contents))

        # Process the image with optional caption
        output_path = process_image(template_path, user_image, caption)

        # Return the result
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Image processed successfully",
                "output_path": output_path,
                "template_used": template_name,
                "template_path": template_path,
                "original_filename": file.filename,
                "file_size": len(contents),
                "original_text": text,
                "parsed_caption": caption,
                "max_uploaded_dimensions": f"{MAX_UPLOADED_WIDTH}x{MAX_UPLOADED_HEIGHT}",
                "final_dimensions": "Match template dimensions",
                "layering": "Template overlaid on uploaded image",
                "text_settings": {
                    "position_y": TEXT_Y_POSITION,
                    "font_size": TEXT_FONT_SIZE,
                    "font": "Inter Bold / Manjari Bold",
                    "alignment": "center",
                    "language_detected": detect_language(caption) if caption else "en",
                    "text_color": "black" if get_text_color(template_path) == (0, 0, 0) else "white"
                }
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.get("/list-processed")
async def list_processed_images():
    """List all processed images in the output directory."""
    try:
        if not os.path.exists(OUTPUT_DIR):
            return {"processed_images": []}

        files = [f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        file_info = []

        for file in files:
            file_path = os.path.join(OUTPUT_DIR, file)
            file_stat = os.stat(file_path)
            file_info.append({
                "filename": file,
                "path": file_path,
                "size": file_stat.st_size,
                "created": datetime.fromtimestamp(file_stat.st_ctime).isoformat()
            })

        return {
            "processed_images": file_info,
            "total_count": len(file_info),
            "max_uploaded_dimensions": f"{MAX_UPLOADED_WIDTH}x{MAX_UPLOADED_HEIGHT}",
            "final_dimensions": "Match template dimensions"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)