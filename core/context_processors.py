"""Company information shared with every template.

Source: docs/Website Basic Information.docx. Edit values here, not in templates.
"""

COMPANY = {
    "name": "Techno Mate Technologies",
    "short_name": "Techno Mate",
    "logo_static_path": "images/techno-mate-logo.png",
    "about": (
        "Techno Mate Technologies supplies equipment and systems across industrial "
        "plant & machinery, energy & power, robotic & automation, steel & metal and "
        "pharma & biotech, backed by installation, spares and technical support."
    ),
    "offices": [
        {
            "label": "Corporate Office",
            "address": "10/G, Azad Center, 55-Purana Paltan, Dhaka-1000, Bangladesh",
        },
        {
            "label": "Chittagong Office",
            "address": "Agarabad Center (9th floor), 2470/A, SK. Mujib Road, Agrabad, Chittagong",
        },
    ],
    "phones": ["02-223352155", "02-223358554"],
    "email": "tmt@chemietradebd.net",
    "youtube_url": "https://www.youtube.com/@TechnoMateTechnologies",
    # Social profiles (docs/Website Basic Information.docx). Only YouTube is
    # published so far; the others stay "#" until the accounts exist.
    "social": [
        {"name": "Facebook", "icon": "facebook", "url": "#", "label": "Facebook"},
        {"name": "YouTube", "icon": "youtube", "url": "https://www.youtube.com/@TechnoMateTechnologies", "label": "YouTube"},
        {"name": "WhatsApp", "icon": "whatsapp", "url": "#", "label": "WhatsApp"},
        {"name": "X", "icon": "x", "url": "#", "label": "X"},
    ],
}


def company(request):
    return {"company": COMPANY}
