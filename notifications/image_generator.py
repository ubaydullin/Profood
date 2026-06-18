import io
import asyncio
import aiohttp
from PIL import Image, ImageDraw, ImageFont

async def fetch_image(url: str) -> Image.Image | None:
    if not url:
        return None
    if url.startswith("/"):
        url = "https://eda.yandex.uz" + url
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.read()
                    return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception as e:
        print(f"Failed to fetch product image from {url}: {e}")
    return None

def hex_to_rgb(hex_str: str):
    h = hex_str.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _render_card_sync(
    vendor_name: str,
    item_name: str,
    old_price: float,
    new_price: float,
    discount: float,
    aggregator: str,
    product_img: Image.Image | None
) -> io.BytesIO:
    width, height = 800, 600
    
    # Yandex Design System Colors
    yandex_yellow = hex_to_rgb("#FCE000")
    yandex_red = hex_to_rgb("#FA4A33")
    text_black = hex_to_rgb("#000000")
    card_bg = hex_to_rgb("#FFFFFF")
    uzum_color = hex_to_rgb("#8A2BE2") # fallback for Uzum
    corner_radius = 16
    
    img = Image.new("RGBA", (width, height), color=(*card_bg, 255))

    # Paste product image on the TOP HALF
    half_h = 320
    if product_img:
        try:
            ratio = max(width / product_img.width, half_h / product_img.height)
            new_w = int(product_img.width * ratio)
            new_h = int(product_img.height * ratio)
            product_img = product_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            # Center crop
            left = (new_w - width) // 2
            top = (new_h - half_h) // 2
            product_img = product_img.crop((left, top, left + width, top + half_h))
            
            img.paste(product_img, (0, 0), product_img if product_img.mode == 'RGBA' else None)
        except Exception as e:
            print(f"Error compositing image: {e}")
    else:
        # If no image, fill top half with a generic pleasant gray/gradient
        draw_temp = ImageDraw.Draw(img)
        draw_temp.rectangle([0, 0, width, half_h], fill=(240, 240, 240, 255))

    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)

    # Load fonts
    try:
        font_xlarge = ImageFont.truetype("arial.ttf", 60)
        font_large = ImageFont.truetype("arial.ttf", 50)
        font_medium = ImageFont.truetype("arial.ttf", 35)
        font_strike = ImageFont.truetype("arial.ttf", 30)
        font_small = ImageFont.truetype("arial.ttf", 25)
    except IOError:
        font_xlarge = font_large = font_medium = font_strike = font_small = ImageFont.load_default()

    # Draw aggregator badge (Top Right inside image)
    is_yandex = aggregator.lower().startswith("yandex")
    agg_color = yandex_yellow if is_yandex else uzum_color
    badge_w, badge_h = 160, 50
    badge_x, badge_y = width - badge_w - 20, 20
    draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], radius=corner_radius, fill=agg_color)
    
    badge_text_color = text_black if is_yandex else (255, 255, 255)
    try:
        text_bbox = draw.textbbox((0, 0), aggregator.upper(), font=font_small)
        text_w = text_bbox[2] - text_bbox[0]
        draw.text((badge_x + (badge_w - text_w) // 2, badge_y + 10), aggregator.upper(), fill=badge_text_color, font=font_small)
    except Exception:
        draw.text((badge_x + 20, badge_y + 10), aggregator[:10], fill=badge_text_color, font=font_small)

    # ------------------ TEXT SECTION (BOTTOM HALF) ------------------
    text_start_y = half_h + 30
    
    # Vendor Name
    draw.text((40, text_start_y), str(vendor_name).upper(), fill=(130, 130, 130), font=font_medium)

    # Item Name
    item_name_str = str(item_name)
    try:
        if len(item_name_str) > 38:
            item_name_str = item_name_str[:35] + "..."
    except Exception:
        pass
    draw.text((40, text_start_y + 50), item_name_str, fill=text_black, font=font_large)

    # Draw Discount Badge
    disc_x, disc_y = 40, text_start_y + 130
    disc_w, disc_h = 160, 80
    draw.rounded_rectangle([disc_x, disc_y, disc_x + disc_w, disc_y + disc_h], radius=corner_radius, fill=yandex_red)
    discount_text = f"-{int(discount)}%"
    
    try:
        text_bbox = draw.textbbox((0, 0), discount_text, font=font_large)
        text_w = text_bbox[2] - text_bbox[0]
        draw.text((disc_x + (disc_w - text_w) // 2, disc_y + 15), discount_text, fill=(255, 255, 255), font=font_large)
    except Exception:
        draw.text((disc_x + 20, disc_y + 15), discount_text, fill=(255, 255, 255), font=font_large)

    # Draw Prices
    old_price_str = f"{int(old_price):,} сум".replace(",", " ")
    new_price_str = f"{int(new_price):,} сум".replace(",", " ")

    price_x = 230
    price_y = disc_y

    # Old price with red strikethrough
    draw.text((price_x, price_y), old_price_str, fill=(150, 150, 150), font=font_strike)
    try:
        text_bbox = draw.textbbox((price_x, price_y), old_price_str, font=font_strike)
        line_y = text_bbox[1] + (text_bbox[3] - text_bbox[1]) // 2
        draw.line([text_bbox[0], line_y, text_bbox[2], line_y], fill=yandex_red, width=3)
    except Exception:
        draw.line([price_x, price_y + 15, price_x + 150, price_y + 15], fill=yandex_red, width=3)

    # New price
    draw.text((price_x, price_y + 35), new_price_str, fill=text_black, font=font_xlarge)

    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

async def generate_item_card(
    vendor_name: str,
    item_name: str,
    old_price: float,
    new_price: float,
    discount: float,
    aggregator: str = "Unknown",
    picture_url: str | None = None,
) -> io.BytesIO:
    """
    Asynchronously generates a promotional image card using the new Yandex Design System.
    """
    product_img = None
    if picture_url:
        product_img = await fetch_image(picture_url)
        
    return await asyncio.to_thread(
        _render_card_sync,
        vendor_name,
        item_name,
        old_price,
        new_price,
        discount,
        aggregator,
        product_img
    )
