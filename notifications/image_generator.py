import io
from PIL import Image, ImageDraw, ImageFont


def generate_promo_image(
    restaurant_name: str,
    item_name: str,
    old_price: float,
    new_price: float,
    discount: float,
) -> io.BytesIO:
    """
    Generates a promotional image card for a discount.
    Returns an io.BytesIO object containing the PNG image.
    """
    width, height = 800, 400
    # Background color: dark modern slate
    img = Image.new("RGB", (width, height), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)

    # Load fonts (fallback to default if arial is not found)
    try:
        font_large = ImageFont.truetype("arial.ttf", 60)
        font_medium = ImageFont.truetype("arial.ttf", 40)
        font_strike = ImageFont.truetype("arial.ttf", 35)
    except IOError:
        # Fallback to default (won't look as good, might struggle with cyrillic, but safe)
        font_large = font_medium = font_strike = ImageFont.load_default()

    # Draw restaurant name
    draw.text(
        (40, 40), str(restaurant_name).upper(), fill=(255, 200, 0), font=font_large
    )

    # Draw item name
    item_name_str = str(item_name)
    if len(item_name_str) > 35:
        item_name_str = item_name_str[:32] + "..."
    draw.text((40, 120), item_name_str, fill=(255, 255, 255), font=font_medium)

    # Draw discount badge (red rounded rectangle)
    badge_x, badge_y = 40, 200
    badge_width = 220
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_width, badge_y + 80],
        radius=15,
        fill=(220, 53, 69),
    )

    discount_text = f"-{discount}%"
    # Simple centering approximation for the badge text
    draw.text(
        (badge_x + 20, badge_y + 10),
        discount_text,
        fill=(255, 255, 255),
        font=font_large,
    )

    # Draw prices
    old_price_str = f"{int(old_price):,} сум".replace(",", " ")
    new_price_str = f"{int(new_price):,} сум".replace(",", " ")

    price_x = 300
    price_y = 200

    # Old price
    draw.text((price_x, price_y), old_price_str, fill=(150, 150, 150), font=font_strike)
    # Strikethrough line
    text_bbox = draw.textbbox((price_x, price_y), old_price_str, font=font_strike)
    draw.line(
        [
            text_bbox[0],
            text_bbox[1] + (text_bbox[3] - text_bbox[1]) // 2,
            text_bbox[2],
            text_bbox[1] + (text_bbox[3] - text_bbox[1]) // 2,
        ],
        fill=(220, 53, 69),
        width=3,
    )

    # New price
    draw.text(
        (price_x, price_y + 60), new_price_str, fill=(0, 255, 100), font=font_large
    )

    # Save to BytesIO
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio
