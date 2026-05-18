import re
from typing import Dict, Any


def _choose_pleasant_color(property_name: str, current_state: Dict[str, Any]) -> str:
    if property_name == "background_color":
        current = (current_state or {}).get("background_color")
        palette = ["#F5F7FA", "#E8F4FD", "#F6F0FF", "#FFF4E6", "#EAF7EA"]
        for c in palette:
            if c != current:
                return c
        return "#F5F7FA"
    if property_name == "text_color":
        return "#1F2937"
    return "#F5F7FA"


def inspect_state(path: str, content: str) -> Dict[str, Any]:
    body_bg = None
    text_color = None
    font_size_px = None
    text = None

    m = re.search(r'background-color\s*:\s*([^;\"]+)', content, re.I)
    if m:
        body_bg = m.group(1).strip()

    h1_match = re.search(r'<h1([^>]*)>(.*?)</h1>', content, re.I | re.S)
    if h1_match:
        attrs = h1_match.group(1) or ""
        text = re.sub(r'<.*?>', '', h1_match.group(2) or '').strip()
        cm = re.search(r'color\s*:\s*([^;\"]+)', attrs, re.I)
        if cm:
            text_color = cm.group(1).strip()
        fm = re.search(r'font-size\s*:\s*(\d+)px', attrs, re.I)
        if fm:
            font_size_px = int(fm.group(1))

    return {
        "path": path,
        "kind": "html",
        "focus": "primary_text",
        "state": {
            "text": text,
            "font_size_px": font_size_px,
            "text_color": text_color,
            "background_color": body_bg,
        }
    }


def apply_edit(path: str, content: str, scope: str, property_name: str, operation: str, value: Any) -> Dict[str, Any]:
    updated = content

    if property_name == "background_color" and operation in ("set", "choose_and_set"):
        if operation == "choose_and_set" or value in (None, "", "agent_choice"):
            value = _choose_pleasant_color(property_name, inspect_state(path, updated).get("state", {}))
        if '<body style="' in updated:
            if 'background-color:' in updated:
                updated = re.sub(r'background-color\s*:\s*[^;\"]+;?', f'background-color: {value};', updated, flags=re.I)
            else:
                updated = updated.replace('<body style="', f'<body style="background-color: {value}; ')
        else:
            updated = updated.replace('<body>', f'<body style="background-color: {value};">')

    elif property_name == "text_color" and operation == "set":
        h1_match = re.search(r'<h1([^>]*)>', updated, re.I)
        if h1_match:
            tag = h1_match.group(0)
            attrs = h1_match.group(1) or ""
            if 'style="' in tag:
                if 'color:' in tag:
                    new_tag = re.sub(r'color\s*:\s*[^;\"]+;?', f'color: {value};', tag, flags=re.I)
                else:
                    new_tag = tag.replace('style="', f'style="color: {value}; ')
            else:
                new_tag = tag.replace('<h1', f'<h1 style="color: {value};"')
            updated = updated.replace(tag, new_tag, 1)

    elif property_name == "font_size":
        h1_match = re.search(r'<h1([^>]*)>', updated, re.I)
        if h1_match:
            tag = h1_match.group(0)
            size_match = re.search(r'font-size\s*:\s*(\d+)px', tag, re.I)
            current = int(size_match.group(1)) if size_match else 16
            if operation == "scale":
                new_size = int(current * float(value))
            else:
                new_size = int(value)
            if 'style="' in tag:
                if 'font-size:' in tag:
                    new_tag = re.sub(r'font-size\s*:\s*\d+px;?', f'font-size: {new_size}px;', tag, flags=re.I)
                else:
                    new_tag = tag.replace('style="', f'style="font-size: {new_size}px; ')
            else:
                new_tag = tag.replace('<h1', f'<h1 style="font-size: {new_size}px;"')
            updated = updated.replace(tag, new_tag, 1)

    elif property_name == "text_content" and operation == "set":
        updated = re.sub(r'(<h1[^>]*>)(.*?)(</h1>)', rf'\1{value}\3', updated, count=1, flags=re.I | re.S)

    return {
        "path": path,
        "content": updated,
        "state": inspect_state(path, updated),
    }
