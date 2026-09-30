import os
import math
from PIL import Image, ImageDraw, ImageFont

def create_maxflow_logo(output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 800 x 300 canvas with transparent/white background
    width, height = 800, 320
    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Colors matching the logo
    blue = (0, 114, 206, 255)      # #0072ce
    grey = (112, 117, 122, 255)    # #70757a
    light_grey = (180, 184, 188, 255)

    # Center coordinates
    cx, cy = width // 2, height // 2

    # Draw Orbital Swooshes (Elliptical Arcs)
    # Upper-Right Arc (Grey & Blue)
    # Tilted ellipse arc using polygon / bezier points
    def get_ellipse_points(cx, cy, rx, ry, start_angle, end_angle, tilt_deg):
        points = []
        tilt_rad = math.radians(tilt_deg)
        cos_t = math.cos(tilt_rad)
        sin_t = math.sin(tilt_rad)
        for deg in range(start_angle, end_angle + 1, 2):
            rad = math.radians(deg)
            x = rx * math.cos(rad)
            y = ry * math.sin(rad)
            # Rotate
            xr = cx + (x * cos_t - y * sin_t)
            yr = cy + (x * sin_t + y * cos_t)
            points.append((xr, yr))
        return points

    # Draw Upper Arc (Grey outer, Blue inner)
    grey_arc_top = get_ellipse_points(cx, cy - 5, 220, 95, 200, 360, -22)
    draw.line(grey_arc_top, fill=grey, width=12, joint="curve")
    
    blue_arc_top = get_ellipse_points(cx, cy - 10, 190, 80, 210, 340, -22)
    draw.line(blue_arc_top, fill=blue, width=14, joint="curve")

    # Draw Lower Arc (Blue outer, Grey inner)
    blue_arc_bottom = get_ellipse_points(cx, cy + 5, 220, 95, 20, 180, -22)
    draw.line(blue_arc_bottom, fill=blue, width=14, joint="curve")

    grey_arc_bottom = get_ellipse_points(cx, cy + 10, 190, 80, 30, 160, -22)
    draw.line(grey_arc_bottom, fill=light_grey, width=10, joint="curve")

    # Load Font
    font_path = "C:\\Windows\\Fonts\\arialbi.ttf" # Arial Bold Italic
    if not os.path.exists(font_path):
        font_path = "C:\\Windows\\Fonts\\arialbd.ttf"
    
    try:
        font = ImageFont.truetype(font_path, 88)
    except:
        font = ImageFont.load_default()

    # Draw text "MAX" in blue and "FLOW" in grey
    # Measure text positions
    max_text = "MAX"
    flow_text = "FLOW"
    
    max_bbox = draw.textbbox((0, 0), max_text, font=font)
    flow_bbox = draw.textbbox((0, 0), flow_text, font=font)
    
    max_w = max_bbox[2] - max_bbox[0]
    flow_w = flow_bbox[2] - flow_bbox[0]
    total_w = max_w + flow_w
    
    start_x = cx - (total_w // 2) - 10
    text_y = cy - 45

    # Draw white background cutout under text for clean overlay
    draw.rectangle([start_x - 15, text_y + 10, start_x + total_w + 15, text_y + 80], fill=(255, 255, 255, 230))

    # Draw MAX in blue
    draw.text((start_x, text_y), max_text, fill=blue, font=font)
    # Draw FLOW in grey
    draw.text((start_x + max_w + 5, text_y), flow_text, fill=grey, font=font)

    # Save crisp logo
    img.save(output_path, "PNG")
    print(f"Saved logo to {output_path}")

if __name__ == "__main__":
    create_maxflow_logo("c:\\Users\\Dell\\OneDrive\\Desktop\\Maxflow Automate\\quotations\\static\\images\\logo.png")
